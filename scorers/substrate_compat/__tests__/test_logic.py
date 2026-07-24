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

_MATRIX_INCLUDE_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    strategy:
      matrix:
        include:
          - juju-channel: 3/stable
          - juju-channel: 4/stable
    with:
      juju-channel: ${{ matrix.juju-channel }}
"""

_INLINE_COMMENTS_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    uses: canonical/operator-workflows/.github/workflows/integration_test.yaml@main
    with:
      juju-channel: 4/stable # current stable track
      use-canonical-k8s: true # use ck8s substrate
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

_BLOCK_SCALAR_RUN_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: |-
          juju bootstrap microk8s
          pytest -m integration
"""

_FOLDED_CK8S_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: >-
          juju bootstrap
          microk8s
      - run: pytest -m integration
"""

_FOLDED_INTEGRATION_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: juju bootstrap microk8s
      - run: >-
          pytest -m
          integration
"""

_QUOTED_CK8S_RUN_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: "juju bootstrap microk8s"
      - run: pytest -m integration
"""

_QUOTED_INTEGRATION_RUN_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: juju bootstrap microk8s
      - run: 'pytest -m integration'
"""

_QUOTED_HEREDOC_TEXT_WORKFLOW = """\
name: Integration Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: juju bootstrap microk8s
      - run: |-
          echo "<<EOF"
          pytest -m integration
"""

_SCRIPT_TEXT_JUJU4_WORKFLOW = """\
name: CI
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: |
          cat <<'EOF'
          juju-channel: 4/stable
          EOF
"""

_NOTE_TEXT_INTEGRATION_WORKFLOW = """\
name: CI
on: [push]
jobs:
  test:
    uses: canonical/operator-workflows/.github/workflows/other.yaml@main
    with:
      juju-channel: 3/stable
      note: "pytest -m integration"
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
    _mock_workflow_file("canonical/synapse-operator", "integration.yaml", _MATRIX_JUJU4_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is True
    assert result["supports_juju_4"] is True
    assert result["substrate_test_evidence_present"] is True


@responses.activate
def test_detects_juju3_and_juju4_from_matrix_include_entries():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "integration.yaml", _MATRIX_INCLUDE_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is True
    assert result["supports_juju_4"] is True
    assert result["substrate_test_evidence_present"] is True


@responses.activate
def test_detects_inline_comments_on_juju_channel_and_ck8s():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "integration.yaml", _INLINE_COMMENTS_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is True
    assert result["substrate_test_evidence_present"] is True
    assert result["uses_canonical_k8s"] is True


@responses.activate
def test_detects_block_scalar_run_commands():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file(
        "canonical/synapse-operator", "integration.yaml", _BLOCK_SCALAR_RUN_WORKFLOW
    )
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is False
    assert result["uses_canonical_k8s"] is True
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
def test_detects_canonical_k8s_from_folded_run_block():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "integration.yaml", _FOLDED_CK8S_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is False
    assert result["uses_canonical_k8s"] is True
    assert result["substrate_test_evidence_present"] is True


@responses.activate
def test_detects_integration_from_folded_run_block():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file(
        "canonical/synapse-operator", "integration.yaml", _FOLDED_INTEGRATION_WORKFLOW
    )
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is False
    assert result["uses_canonical_k8s"] is True
    assert result["substrate_test_evidence_present"] is True


@responses.activate
def test_detects_canonical_k8s_from_quoted_run_scalar():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "integration.yaml", _QUOTED_CK8S_RUN_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is False
    assert result["uses_canonical_k8s"] is True
    assert result["substrate_test_evidence_present"] is True


@responses.activate
def test_detects_integration_from_quoted_run_scalar():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file(
        "canonical/synapse-operator",
        "integration.yaml",
        _QUOTED_INTEGRATION_RUN_WORKFLOW,
    )
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is False
    assert result["uses_canonical_k8s"] is True
    assert result["substrate_test_evidence_present"] is True


@responses.activate
def test_quoted_heredoc_text_does_not_hide_following_integration_command():
    _mock_workflows_dir("canonical/synapse-operator", ["integration.yaml"])
    _mock_workflow_file(
        "canonical/synapse-operator", "integration.yaml", _QUOTED_HEREDOC_TEXT_WORKFLOW
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
def test_script_text_does_not_set_juju_channel():
    _mock_workflows_dir("canonical/synapse-operator", ["ci.yaml"])
    _mock_workflow_file(
        "canonical/synapse-operator",
        "ci.yaml",
        _SCRIPT_TEXT_JUJU4_WORKFLOW,
    )
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is False
    assert result["supports_juju_4"] is False
    assert result["substrate_test_evidence_present"] is False
    assert result["uses_canonical_k8s"] is False


@responses.activate
def test_note_text_does_not_set_integration_evidence():
    _mock_workflows_dir("canonical/synapse-operator", ["ci.yaml"])
    _mock_workflow_file(
        "canonical/synapse-operator",
        "ci.yaml",
        _NOTE_TEXT_INTEGRATION_WORKFLOW,
    )
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is True
    assert result["supports_juju_4"] is False
    assert result["substrate_test_evidence_present"] is False
    assert result["uses_canonical_k8s"] is False


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


_EOF_HYPHEN_HEREDOC_WORKFLOW = """\
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - with:
          juju-channel: 3/stable
        run: |
          cat <<'EOF-YAML' > payload.yaml
          pytest -m integration
          juju bootstrap microk8s
          EOF-YAML
          tox -e lint
"""

_COMMENT_HEREDOC_WORKFLOW = """\
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - with:
          juju-channel: 3/stable
        run: |
          # <<EOF
          pytest -m integration
"""


@responses.activate
def test_heredoc_with_hyphenated_delimiter_skips_payload():
    """Payload inside cat <<'EOF-YAML'...EOF-YAML must not count as commands."""
    _mock_workflows_dir("canonical/synapse-operator", ["ci.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "ci.yaml", _EOF_HYPHEN_HEREDOC_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    # juju-channel 3/stable is real config → juju3 true
    assert result["supports_juju_3"] is True
    # heredoc payload must NOT produce ck8s or integration evidence
    assert result["uses_canonical_k8s"] is False
    # tox -e lint (not integration) is the only real run command → no integration evidence
    assert result["substrate_test_evidence_present"] is False


@responses.activate
def test_shell_comment_heredoc_token_does_not_suppress_real_commands():
    """# <<EOF in a shell comment must not enter heredoc mode."""
    _mock_workflows_dir("canonical/synapse-operator", ["ci.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "ci.yaml", _COMMENT_HEREDOC_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is True
    # pytest -m integration following the comment line must be detected
    assert result["substrate_test_evidence_present"] is True


_DEFAULTS_RUN_WORKFLOW = """\
name: CI
on: [push]
defaults:
  run:
    shell: bash
    working-directory: ./scripts
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - with:
          juju-channel: 3/stable
      - run: pytest -m integration
"""


@responses.activate
def test_defaults_run_mapping_does_not_crash():
    """defaults.run: mapping block must not raise an error."""
    _mock_workflows_dir("canonical/synapse-operator", ["ci.yaml"])
    _mock_workflow_file("canonical/synapse-operator", "ci.yaml", _DEFAULTS_RUN_WORKFLOW)
    result = compute_metrics(UNIT, "token")
    assert result["supports_juju_3"] is True
    assert result["substrate_test_evidence_present"] is True
