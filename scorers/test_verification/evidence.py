"""Fail-closed acquisition of pinned GitHub and public Charmhub testing evidence."""

import base64
from typing import Any
from urllib.parse import quote

import requests
import yaml

from engine.metric_outcomes import MetricOutcome, insufficient_data, measured
from engine.models import EvaluationUnit, ProductType
from scorers.shared.github_signals import (
    build_github_session,
    github_session_get,
    raise_for_required_github_evidence,
)
from scorers.test_verification.v0 import concierge_path, evaluate_checks, normalize, scoped

_API = "https://api.github.com"


class UninterpretableRepository(ValueError):
    """Repository identity or its default branch cannot be resolved."""


def _linked_paths(files: dict[str, str]) -> set[str]:
    from scorers.test_verification.v0 import _directory, _expand, _yaml

    paths: set[str] = set()
    for path, text in files.items():
        if not path.startswith(".github/workflows/"):
            continue
        try:
            workflow = _yaml(text)
            for job in workflow.get("jobs", {}).values():
                for item in _expand(job):
                    directory = _directory(item, workflow)
                    spread_path = normalize(f"{directory}/spread.yaml")
                    if spread_path not in files:
                        continue
                    spread = _yaml(files[spread_path])
                    environments = [spread.get("environment", {})]
                    environments.extend(
                        suite.get("environment", {})
                        for suite in spread.get("integration-suites", {}).values()
                        if isinstance(suite, dict)
                    )
                    for environment in environments:
                        paths.update(
                            normalize(f"{directory}/{concierge_path(value)}")
                            for key, value in environment.items()
                            if (key == "CONCIERGE" or key.startswith("CONCIERGE/"))
                            and isinstance(value, str)
                        )
        except (yaml.YAMLError, ValueError, TypeError, AttributeError):
            # The evaluator reports unknown interpretations; acquisition errors
            # are deliberately outside this catch.
            continue
    return paths


class Evidence:
    def __init__(self, repo: str, token: str | None):
        self.repo = repo
        self.session = build_github_session(token)
        self.base = f"{_API}/repos/{repo}"

    def get(self, path: str, *, optional: bool = False, **params: Any) -> Any:
        url = self.base + path
        response = github_session_get(self.session, url, params=params, timeout=30)
        if optional and response.status_code == 404:
            return None
        raise_for_required_github_evidence(response, url)
        return response.json()

    def pages(self, path: str, key: str | None = None, **params: Any) -> list[dict[str, Any]]:
        entries = []
        page = 1
        while True:
            payload = self.get(path, per_page=100, page=page, **params)
            items = payload.get(key) if key else payload
            if not isinstance(items, list):
                raise ValueError(f"Invalid GitHub list evidence: {path}")
            entries.extend(items)
            if len(items) < 100:
                return entries
            page += 1

    def files(self, sha: str, scope: str) -> dict[str, str]:
        tree = self.get(f"/git/trees/{sha}", recursive=1)
        if tree.get("truncated"):
            raise ValueError("GitHub repository tree was truncated; evidence is incomplete.")
        if not isinstance(tree.get("tree"), list):
            raise ValueError("GitHub repository tree is absent.")
        files = {}
        for entry in tree["tree"]:
            path = entry.get("path", "")
            if entry.get("type") != "blob":
                continue
            name = path.rsplit("/", 1)[-1]
            workflow = path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
            config = name in {"charmcraft.yaml", "metadata.yaml", "spread.yaml"} or (
                "concierge" in name and name.endswith((".yaml", ".yml"))
            )
            component = scoped(path, scope) and (
                path.endswith((".tf", ".tf.json"))
                or path.endswith(".py")
                and "tests" in path.split("/")
            )
            if not (workflow or config or component):
                continue
            blob = self.get(f"/git/blobs/{entry['sha']}")
            if blob.get("encoding") != "base64" or not isinstance(blob.get("content"), str):
                raise ValueError(f"Cannot decode GitHub blob {path}.")
            files[path] = base64.b64decode(blob["content"], validate=False).decode("utf-8")
        for candidate in sorted(_linked_paths(files) - files.keys()):
            matching = next(
                (
                    entry
                    for entry in tree["tree"]
                    if entry.get("path") == candidate and entry.get("type") == "blob"
                ),
                None,
            )
            if matching:
                blob = self.get(f"/git/blobs/{matching['sha']}")
                if blob.get("encoding") != "base64":
                    raise ValueError(f"Cannot decode GitHub blob {candidate}.")
                files[candidate] = base64.b64decode(blob["content"]).decode("utf-8")
        return files

    def required(self, branch: str, branch_data: dict[str, Any]) -> set[str]:
        protection = branch_data.get("protection", {})
        status_checks = protection.get("required_status_checks") or {}
        names = set(status_checks.get("contexts", []))
        names.update(
            check["context"] for check in status_checks.get("checks", []) if check.get("context")
        )
        rules = self.get(f"/rules/branches/{quote(branch, safe='')}")
        if not isinstance(rules, list):
            raise ValueError("Invalid GitHub branch rules evidence.")
        for rule in rules:
            if rule.get("type") == "required_status_checks":
                names.update(
                    check["context"]
                    for check in rule.get("parameters", {}).get("required_status_checks", [])
                    if check.get("context")
                )
        return names

    def ci(self, branch: str, branch_data: dict[str, Any] | None = None) -> MetricOutcome:
        if branch_data is None:
            branch_data = self.get(f"/branches/{quote(branch, safe='')}", optional=True)
        if branch_data is None:
            return insufficient_data(f"Published branch {branch!r} does not exist.")
        sha = branch_data.get("commit", {}).get("sha")
        if not isinstance(sha, str) or not sha:
            return insufficient_data(f"Branch {branch!r} has no identifiable tip.")
        required = self.required(branch, branch_data)
        checks = self.pages(f"/commits/{sha}/check-runs", "check_runs", filter="all")
        statuses = self.pages(f"/commits/{sha}/statuses")
        if not checks and not statuses:
            associated = self.pages(f"/commits/{sha}/pulls")
            matching = [
                pr
                for pr in associated
                if pr.get("merged_at")
                and pr.get("merge_commit_sha") == sha
                and pr.get("base", {}).get("ref") == branch
                and pr.get("base", {}).get("repo", {}).get("full_name") == self.repo
                and pr.get("head", {}).get("sha") == sha
            ]
            if len(matching) != 1:
                return insufficient_data(
                    f"No unambiguous merged PR tested the exact branch {branch!r} tip SHA."
                )
            head = matching[0]["head"]["sha"]
            checks = self.pages(f"/commits/{head}/check-runs", "check_runs", filter="all")
            statuses = self.pages(f"/commits/{head}/statuses")
        return evaluate_checks(checks, statuses=statuses, required=required)


def published_branches(
    unit: EvaluationUnit, files: dict[str, str], default_branch: str
) -> tuple[list[str], MetricOutcome | None]:
    if unit.product_type != ProductType.CHARM:
        return [default_branch], None
    scope = normalize(unit.subpath or ".")
    config_path = normalize(f"{scope}/charmcraft.yaml")
    try:
        charmcraft = yaml.safe_load(files.get(config_path, ""))
        name = charmcraft.get("name") if isinstance(charmcraft, dict) else None
    except yaml.YAMLError:
        name = None
    if not isinstance(name, str) or not name.strip():
        return [default_branch], insufficient_data(
            "Scoped charmcraft.yaml name is absent or invalid."
        )
    response = requests.get(
        f"https://api.charmhub.io/v2/charms/info/{quote(name, safe='')}",
        params={"fields": "channel-map"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    channels = payload.get("channel-map")
    if not isinstance(channels, list):
        return [default_branch], insufficient_data("Charmhub channel-map is not a list.")
    tracks = set()
    for item in channels:
        channel = item.get("channel", {}) if isinstance(item, dict) else {}
        track = channel.get("track") if isinstance(channel, dict) else None
        if not isinstance(track, str) or not track.strip():
            return [default_branch], insufficient_data(
                "Charmhub published track is not identifiable."
            )
        if track != "latest":
            tracks.add(f"track/{track}")
    return [default_branch, *sorted(tracks - {default_branch})], None


def acquire(unit: EvaluationUnit, token: str | None) -> tuple[dict[str, str], MetricOutcome]:
    if not unit.repo:
        raise UninterpretableRepository("Repository is absent.")
    evidence = Evidence(unit.repo, token)
    repository = evidence.get("")
    default = repository.get("default_branch")
    if not isinstance(default, str) or not default:
        raise UninterpretableRepository("Repository default branch is absent.")
    branch_data = evidence.get(f"/branches/{quote(default, safe='')}")
    sha = branch_data.get("commit", {}).get("sha")
    if not isinstance(sha, str) or not sha:
        raise UninterpretableRepository("Default branch tip is absent.")
    files = evidence.files(sha, normalize(unit.subpath or "."))
    branches, unknown = published_branches(unit, files, default)
    outcomes = [
        evidence.ci(branch, branch_data if branch == default else None) for branch in branches
    ]
    if any(outcome.value is False for outcome in outcomes):
        return files, measured(False)
    if unknown is not None:
        return files, unknown
    insufficient = next(
        (outcome for outcome in outcomes if outcome.state.value == "insufficient_data"), None
    )
    return files, insufficient or measured(True)
