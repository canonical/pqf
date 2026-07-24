# scorers/substrate_compat/__tests__/test_logic.py
import base64

import responses

from engine.models import EvaluationUnit, ProductType
from scorers.substrate_compat.logic import compute_metrics

_GITHUB_API = "https://api.github.com"

_JUJU3_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    with:
      juju-channel: 3/stable
"""

_JUJU4_CK8S_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    with:
      juju-channel: 4/stable
      use-canonical-k8s: true
"""

_JUJU24_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    with:
      juju-channel: 24/stable
"""

_MATRIX_JUJU4_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    strategy:
      matrix:
        juju-channel:
          - 3/stable
          - 4/stable
    with:
      juju-channel: ${{ matrix.juju-channel }}
"""

_CANONICAL_K8S_ALIAS_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: juju bootstrap microk8s
      - run: pytest -m integration
"""

_COMMENTED_CANONICAL_K8S_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: |
          # juju bootstrap microk8s
          pytest -m integration
"""

_ECHOED_CANONICAL_K8S_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "juju bootstrap microk8s"
      - run: pytest -m integration
"""

_GENERIC_WORKFLOW = """\
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
def test_detects_juju3_from_workflow():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "integration.yaml", _JUJU3_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is True
    assert result["supports_juju_4"] is False
    assert result["substrate_test_evidence_present"] is True
    assert result["uses_canonical_k8s"] is False


@responses.activate
def test_detects_juju4_from_workflow():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "integration.yaml", _JUJU4_CK8S_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is True


@responses.activate
def test_does_not_treat_juju24_as_juju4():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "integration.yaml", _JUJU24_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is False
    assert result["substrate_test_evidence_present"] is False


@responses.activate
def test_detects_ck8s_from_workflow():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "integration.yaml", _JUJU4_CK8S_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result["uses_canonical_k8s"] is True
    assert result["substrate_test_evidence_present"] is True


@responses.activate
def test_detects_juju4_from_matrix_values():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file(
        "canonical/synapse-operator", "integration.yaml", _MATRIX_JUJU4_WORKFLOW
    )
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is True
    assert result["supports_juju_4"] is True
    assert result["substrate_test_evidence_present"] is True


@responses.activate
def test_detects_canonical_k8s_alias_from_bootstrap_command():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file(
        "canonical/synapse-operator", "integration.yaml", _CANONICAL_K8S_ALIAS_WORKFLOW
    )
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is False
    assert result["uses_canonical_k8s"] is True
    assert result["substrate_test_evidence_present"] is True


@responses.activate
def test_comment_does_not_set_canonical_k8s():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file(
        "canonical/synapse-operator",
        "integration.yaml",
        _COMMENTED_CANONICAL_K8S_WORKFLOW,
    )
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is False
    assert result["uses_canonical_k8s"] is False
    assert result["substrate_test_evidence_present"] is False


@responses.activate
def test_echo_does_not_set_canonical_k8s():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file(
        "canonical/synapse-operator",
        "integration.yaml",
        _ECHOED_CANONICAL_K8S_WORKFLOW,
    )
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is False
    assert result["uses_canonical_k8s"] is False
    assert result["substrate_test_evidence_present"] is False


@responses.activate
def test_generic_workflow_sets_no_flags():
    _mock_workflows_dir("canonical/synapse-operator", ["ci.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "ci.yaml", _GENERIC_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result == {
        "supports_juju_3": False,
        "supports_juju_4": False,
        "substrate_test_evidence_present": False,
        "uses_canonical_k8s": False,
    }


@responses.activate
def test_missing_workflows_dir_returns_false():
    responses.add(
        responses.GET,
        f"{_GITHUB_API}/repos/canonical/synapse-operator/contents/.github/workflows",
        status=404,
    )
    result = compute_metrics(UNIT, "token")
    assert result == {
        "supports_juju_3": False,
        "supports_juju_4": False,
        "substrate_test_evidence_present": False,
        "uses_canonical_k8s": False,
    }


def test_returns_defaults_when_repo_empty():
    result = compute_metrics(UNIT_EMPTY, "token")
    assert result == {
        "supports_juju_3": False,
        "supports_juju_4": False,
        "substrate_test_evidence_present": False,
        "uses_canonical_k8s": False,
    }
