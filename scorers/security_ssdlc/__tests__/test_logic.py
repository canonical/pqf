import base64

import responses

from engine.models import EvaluationUnit, ProductType
from scorers.security_ssdlc.logic import (
    _has_branch_protection_required_checks,
    compute_metrics,
)

_GITHUB_API = "https://api.github.com"

_CODEQL_WORKFLOW = """\
name: CodeQL
on: [push]
jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: github/codeql-action/init@v3
"""

_NO_CODEQL_WORKFLOW = """\
name: CI
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: echo lint
"""


def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def _mock_dependabot(owner_repo: str, exists: bool):
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/{owner_repo}/contents/.github/dependabot.yml",
        json={"name": "dependabot.yml"} if exists else {},
        status=200 if exists else 404,
    )


def _mock_workflows_dir(owner_repo: str, filenames: list[str]):
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/{owner_repo}/contents/.github/workflows",
        json=[
            {
                "name": name,
                "type": "file",
                "url": f"{_GITHUB_API}/repos/{owner_repo}/contents/.github/workflows/{name}",
            }
            for name in filenames
        ],
        status=200,
    )


def _mock_workflow_file(owner_repo: str, filename: str, content: str):
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/{owner_repo}/contents/.github/workflows/{filename}",
        json={"content": _b64(content), "encoding": "base64"},
        status=200,
    )


def _mock_repo(owner_repo: str, default_branch: str = "main"):
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/{owner_repo}",
        json={"default_branch": default_branch},
        status=200,
    )


def _mock_branch_protection(
    owner_repo: str,
    default_branch: str = "main",
    required_status_checks: dict | None = None,
):
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/{owner_repo}/branches/{default_branch}/protection",
        json={"required_status_checks": required_status_checks or {}},
        status=200,
    )


UNIT = EvaluationUnit(
    product_id="synapse",
    product_type=ProductType.CHARM,
    repo="canonical/synapse-operator",
)

UNIT_EMPTY = EvaluationUnit(
    product_id="synapse",
    product_type=ProductType.CHARM,
    repo="",
)


@responses.activate
def test_dependabot_enabled_when_file_exists():
    _mock_dependabot("canonical/synapse-operator", exists=True)
    _mock_workflows_dir("canonical/synapse-operator", ["ci.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "ci.yaml", _NO_CODEQL_WORKFLOW)
    _mock_repo("canonical/synapse-operator")
    _mock_branch_protection("canonical/synapse-operator")
    result = compute_metrics(UNIT, "token")
    assert result["dependabot_enabled"] is True
    assert result["branch_protection_required_checks"] is False


@responses.activate
def test_dependabot_disabled_on_404():
    _mock_dependabot("canonical/synapse-operator", exists=False)
    _mock_workflows_dir("canonical/synapse-operator", ["ci.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "ci.yaml", _NO_CODEQL_WORKFLOW)
    _mock_repo("canonical/synapse-operator")
    _mock_branch_protection("canonical/synapse-operator")
    result = compute_metrics(UNIT, "token")
    assert result["dependabot_enabled"] is False
    assert result["branch_protection_required_checks"] is False


@responses.activate
def test_codeql_enabled_when_workflow_contains_action():
    _mock_dependabot("canonical/synapse-operator", exists=False)
    _mock_workflows_dir("canonical/synapse-operator", ["codeql.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "codeql.yaml", _CODEQL_WORKFLOW)
    _mock_repo("canonical/synapse-operator")
    _mock_branch_protection("canonical/synapse-operator")
    result = compute_metrics(UNIT, "token")
    assert result["codeql_enabled"] is True
    assert result["branch_protection_required_checks"] is False


@responses.activate
def test_codeql_disabled_when_action_absent():
    _mock_dependabot("canonical/synapse-operator", exists=False)
    _mock_workflows_dir("canonical/synapse-operator", ["ci.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "ci.yaml", _NO_CODEQL_WORKFLOW)
    _mock_repo("canonical/synapse-operator")
    _mock_branch_protection("canonical/synapse-operator")
    result = compute_metrics(UNIT, "token")
    assert result["codeql_enabled"] is False
    assert result["branch_protection_required_checks"] is False


@responses.activate
def test_branch_protection_required_checks_true():
    _mock_repo("canonical/test-repo")
    _mock_branch_protection(
        "canonical/test-repo",
        required_status_checks={"contexts": ["ci/test"], "checks": []},
    )
    result = _has_branch_protection_required_checks("canonical/test-repo", "token")
    assert result is True


def test_returns_defaults_when_repo_empty():
    result = compute_metrics(UNIT_EMPTY, "token")
    assert result == {
        "dependabot_enabled": False,
        "codeql_enabled": False,
        "branch_protection_required_checks": False,
    }


def test_dimensions_yaml_mentions_new_ssdlc_metrics():
    import yaml
    from pathlib import Path

    data = yaml.safe_load(Path("config/dimensions.yaml").read_text())
    outputs = data["dimensions"]["security_ssdlc"]["outputs"]
    assert "renovate_enabled" in outputs
    assert "canonical_repo_automation_registered" in outputs
    assert "sast_workflow_present" in outputs
