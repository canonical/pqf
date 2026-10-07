import pytest
import responses
import yaml

from engine.metric_outcomes import MetricState, measured
from engine.models import EvaluationUnit, ProductType
from scorers.security_ssdlc.logic import (
    _has_branch_protection_required_checks,
    _is_registered_in_repo_automation,
    compute_metrics,
)


class _Response:
    def __init__(self, ok: bool, payload: dict):
        self.ok = ok
        self.status_code = 200 if ok else 404
        self._payload = payload

    def json(self):
        return self._payload


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


def test_branch_protection_required_checks_true(mocker):
    def fake_github_get(url, token, accept=None):
        if url.endswith("/repos/canonical/test-repo"):
            return _Response(True, {"default_branch": "main"})
        return _Response(True, {"required_status_checks": {"contexts": ["ci/test"], "checks": []}})

    mocker.patch("scorers.security_ssdlc.logic.github_get", side_effect=fake_github_get)
    assert _has_branch_protection_required_checks("canonical/test-repo", "token") is True


def test_repo_automation_registration_reads_from_authoritative_list(mocker):
    registration_path = "groups/is/platform-engineering/repos/saml-integrator-operator/inputs.hcl"
    mocker.patch(
        "scorers.security_ssdlc.logic.github_get",
        side_effect=[
            _Response(True, {"default_branch": "main"}),
            _Response(
                True,
                {
                    "tree": [
                        {
                            "type": "blob",
                            "path": registration_path,
                        }
                    ]
                },
            ),
        ],
    )
    assert _is_registered_in_repo_automation("canonical/saml-integrator-operator", "token") is True


def test_repo_automation_registration_returns_false_when_file_absent(mocker):
    mocker.patch(
        "scorers.security_ssdlc.logic.github_get",
        side_effect=[
            _Response(True, {"default_branch": "main"}),
            _Response(True, {"tree": []}),  # no config file in tree
        ],
    )
    assert _is_registered_in_repo_automation("canonical/saml-integrator-operator", "token") is False


def test_repo_automation_registration_returns_false_for_non_canonical_owner(mocker):
    assert _is_registered_in_repo_automation("thirdparty/some-operator", "token") is False


def test_compute_metrics_detects_new_ssdlc_signals(mocker):
    mocker.patch(
        "scorers.security_ssdlc.logic.repo_file_exists",
        side_effect=lambda repo, path, token: path in {".github/renovate.json", "SECURITY.md"},
    )
    mocker.patch(
        "scorers.security_ssdlc.logic.repo_file_text",
        return_value="We track CVEs and vulnerability disclosures.",
    )
    mocker.patch(
        "scorers.security_ssdlc.logic._is_registered_in_repo_automation",
        return_value=True,
    )
    mocker.patch(
        "scorers.security_ssdlc.logic.workflow_files",
        return_value=[("security.yaml", "uses: github/codeql-action/init@v3")],
    )
    mocker.patch(
        "scorers.security_ssdlc.logic.github_get",
        side_effect=[
            # For _has_signed_commits_required
            _Response(True, {"default_branch": "main"}),
            _Response(True, {"required_signatures": {"enabled": True}}),
            # For _has_branch_protection_required_checks
            _Response(True, {"default_branch": "main"}),
            _Response(True, {"required_status_checks": {"contexts": ["ci"], "checks": []}}),
        ],
    )

    result = compute_metrics(UNIT, "token")
    assert result == {
        key: measured(value)
        for key, value in {
            "renovate_enabled": True,
            "canonical_repo_automation_registered": True,
            "branch_protection_required_checks": True,
            "signed_commits_required": True,
            "sast_workflow_present": True,
            "cve_tracking_process_present": True,
        }.items()
    }


def test_compute_metrics_falls_back_to_false_when_signals_absent(mocker):
    mocker.patch("scorers.security_ssdlc.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.security_ssdlc.logic.repo_file_text", return_value="")
    mocker.patch("scorers.security_ssdlc.logic.search_code_count", return_value=0)
    mocker.patch(
        "scorers.security_ssdlc.logic._is_registered_in_repo_automation",
        return_value=False,
    )
    mocker.patch("scorers.security_ssdlc.logic.workflow_files", return_value=[])
    mocker.patch(
        "scorers.security_ssdlc.logic.github_get",
        side_effect=[
            # For _has_signed_commits_required
            _Response(True, {"default_branch": "main"}),
            _Response(True, {}),
            # For _has_branch_protection_required_checks
            _Response(True, {"default_branch": "main"}),
            _Response(True, {"required_status_checks": {}}),
        ],
    )
    result = compute_metrics(UNIT, "token")
    assert result == {
        key: measured(value)
        for key, value in {
            "renovate_enabled": False,
            "canonical_repo_automation_registered": False,
            "branch_protection_required_checks": False,
            "signed_commits_required": False,
            "sast_workflow_present": False,
            "cve_tracking_process_present": False,
        }.items()
    }


def test_cve_tracking_detects_non_security_marker(mocker):
    mocker.patch(
        "scorers.security_ssdlc.logic.repo_file_exists",
        side_effect=lambda repo, path, token: path == "docs/cve.md",
    )
    mocker.patch("scorers.security_ssdlc.logic.repo_file_text", return_value="")
    mocker.patch("scorers.security_ssdlc.logic.search_code_count", return_value=0)
    mocker.patch(
        "scorers.security_ssdlc.logic._is_registered_in_repo_automation",
        return_value=False,
    )
    mocker.patch("scorers.security_ssdlc.logic.workflow_files", return_value=[])
    mocker.patch(
        "scorers.security_ssdlc.logic.github_get",
        side_effect=[
            # For _has_signed_commits_required
            _Response(True, {"default_branch": "main"}),
            _Response(True, {}),
            # For _has_branch_protection_required_checks
            _Response(True, {"default_branch": "main"}),
            _Response(True, {"required_status_checks": {}}),
        ],
    )
    result = compute_metrics(UNIT, "token")
    assert result["cve_tracking_process_present"] == measured(True)


def test_returns_defaults_when_repo_empty():
    result = compute_metrics(UNIT_EMPTY, "token")
    assert all(outcome.state == MetricState.NOT_APPLICABLE for outcome in result.values())


def test_framework_contracts_declare_ssdlc_metrics():
    from pathlib import Path

    contracts = sorted(Path("framework/versions").glob("*/dimensions.yaml"))
    assert contracts, "expected at least one framework contract"

    for contract in contracts:
        data = yaml.safe_load(contract.read_text())
        outputs = data["dimensions"]["security_ssdlc"]["outputs"]
        for key in (
            "renovate_enabled",
            "branch_protection_required_checks",
            "signed_commits_required",
        ):
            assert key in outputs, f"{contract} security_ssdlc is missing {key}"

    v1_outputs = yaml.safe_load(Path("framework/versions/v1/dimensions.yaml").read_text())[
        "dimensions"
    ]["security_ssdlc"]["outputs"]
    assert "sast_workflow_present" in v1_outputs
    assert "cve_tracking_process_present" in v1_outputs


def test_signed_commits_required_true(mocker):
    """Signed commits should be True when branch protection requires them."""
    mocker.patch("scorers.security_ssdlc.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.security_ssdlc.logic.search_code_count", return_value=0)
    mocker.patch("scorers.security_ssdlc.logic.workflow_files", return_value=[])
    mocker.patch(
        "scorers.security_ssdlc.logic._is_registered_in_repo_automation", return_value=False
    )

    def fake_github_get(url, token, accept=None):
        if url.endswith("/repos/canonical/synapse-operator"):
            return _Response(True, {"default_branch": "main"})
        if url.endswith("/branches/main/protection"):
            return _Response(
                True,
                {
                    "required_status_checks": {"contexts": ["ci/test"], "checks": []},
                    "required_signatures": {"enabled": True},
                },
            )
        return _Response(False, {})

    mocker.patch("scorers.security_ssdlc.logic.github_get", side_effect=fake_github_get)
    result = compute_metrics(UNIT, "token")
    assert result["signed_commits_required"] == measured(True)


def test_signed_commits_required_false_when_not_configured(mocker):
    """Signed commits should be False when not configured."""
    mocker.patch("scorers.security_ssdlc.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.security_ssdlc.logic.search_code_count", return_value=0)
    mocker.patch("scorers.security_ssdlc.logic.workflow_files", return_value=[])
    mocker.patch(
        "scorers.security_ssdlc.logic._is_registered_in_repo_automation", return_value=False
    )

    def fake_github_get(url, token, accept=None):
        if url.endswith("/repos/canonical/synapse-operator"):
            return _Response(True, {"default_branch": "main"})
        if url.endswith("/branches/main/protection"):
            return _Response(True, {"required_status_checks": {"contexts": ["ci"], "checks": []}})
        return _Response(False, {})

    mocker.patch("scorers.security_ssdlc.logic.github_get", side_effect=fake_github_get)
    result = compute_metrics(UNIT, "token")
    assert result["signed_commits_required"] == measured(False)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
@pytest.mark.parametrize("signal", ["signatures", "checks", "automation"])
@responses.activate
def test_immutable_evidence_acquisition_errors_abort(status, signal):
    from scorers.security_ssdlc.logic import _has_signed_commits_required
    from scorers.shared.github_signals import GitHubAcquisitionError

    if signal == "automation":
        repo = "canonical/canonical-repo-automation"
        helper = _is_registered_in_repo_automation
        path = "/git/trees/main?recursive=1"
    else:
        repo = "canonical/test"
        helper = (
            _has_signed_commits_required
            if signal == "signatures"
            else _has_branch_protection_required_checks
        )
        path = "/branches/main/protection"
    responses.get(f"https://api.github.com/repos/{repo}", json={"default_branch": "main"})
    responses.get(f"https://api.github.com/repos/{repo}{path}", status=status)
    with pytest.raises(GitHubAcquisitionError):
        helper("canonical/test", "token")


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
@pytest.mark.parametrize("signal", ["file_exists", "file_text", "workflows", "search"])
@responses.activate
def test_immutable_extra_signals_do_not_use_failure_shaped_fallbacks(status, signal):
    from scorers.security_ssdlc import logic
    from scorers.shared.github_signals import GitHubAcquisitionError

    helpers = {
        "file_exists": (logic.repo_file_exists, ("canonical/test", "SECURITY.md", "token")),
        "file_text": (logic.repo_file_text, ("canonical/test", "SECURITY.md", "token")),
        "workflows": (logic.workflow_files, ("canonical/test", "token")),
        "search": (logic.search_code_count, ("repo:canonical/test renovate", "token")),
    }
    paths = {
        "file_exists": "/repos/canonical/test/contents/SECURITY.md",
        "file_text": "/repos/canonical/test/contents/SECURITY.md",
        "workflows": "/repos/canonical/test/contents/.github/workflows",
        "search": "/search/code",
    }
    responses.get(f"https://api.github.com{paths[signal]}", status=status)
    helper, args = helpers[signal]
    with pytest.raises(GitHubAcquisitionError):
        helper(*args)
