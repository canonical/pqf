# scorers/substrate_compat/logic.py
import base64
import re
from typing import Any

import requests

from engine.models import EvaluationUnit

_GITHUB_API = "https://api.github.com"


def _make_github_session(github_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    return session


def _fetch_workflow_contents(owner_repo: str, github_token: str) -> list[str]:
    """Fetch text contents of all workflow YAML files in .github/workflows/."""
    session = _make_github_session(github_token)
    list_resp = session.get(
        f"{_GITHUB_API}/repos/{owner_repo}/contents/.github/workflows",
        timeout=15,
    )
    if not list_resp.ok:
        return []
    contents = []
    for entry in list_resp.json():
        if entry.get("type") != "file":
            continue
        name = entry.get("name", "")
        if not (name.endswith(".yml") or name.endswith(".yaml")):
            continue
        file_resp = session.get(entry["url"], timeout=15)
        if file_resp.ok:
            data = file_resp.json()
            raw = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
            contents.append(raw)
    return contents


def compute_metrics(unit: EvaluationUnit, github_token: str) -> dict[str, Any]:
    """
    Determine substrate compatibility by scanning GitHub workflow files.

    supports_juju_3: any workflow matches juju-channel:.*3/stable
    supports_juju_4: any workflow matches juju-channel:.*4/stable
    supports_ck8s:   any workflow contains use-canonical-k8s: true
    """
    supports_juju_3 = False
    supports_juju_4 = False
    supports_ck8s = False

    if unit.repo:
        for content in _fetch_workflow_contents(unit.repo, github_token):
            if re.search(r"juju-channel:.*3/stable", content):
                supports_juju_3 = True
            if re.search(r"juju-channel:.*4/stable", content):
                supports_juju_4 = True
            if "use-canonical-k8s: true" in content:
                supports_ck8s = True

    return {
        "supports_juju_3": supports_juju_3,
        "supports_juju_4": supports_juju_4,
        "supports_ck8s": supports_ck8s,
    }
