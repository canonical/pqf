"""Fail-closed acquisition of pinned GitHub testing evidence."""

import base64
from typing import Any
from urllib.parse import quote

import yaml

from engine.models import EvaluationUnit
from scorers.shared.github_signals import (
    build_github_session,
    github_session_get,
    raise_for_required_github_evidence,
)
from scorers.test_verification.v0 import concierge_path, normalize, scoped

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
                        backend.get("environment", {})
                        for backend in spread.get("backends", {}).values()
                        if isinstance(backend, dict)
                    )
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


def acquire(unit: EvaluationUnit, token: str | None) -> dict[str, str]:
    """Return the scoped default-branch files needed by the V0 testing checks."""
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
    return evidence.files(sha, normalize(unit.subpath or "."))
