import pytest
import responses
import yaml

from engine.models import EvaluationUnit, ProductType
from scorers.security_ssdlc.logic import (
    _has_branch_protection_required_checks,
    _has_signed_commits_required,
    _is_registered_in_repo_automation,
    compute_metrics,
)
from scorers.shared.github_signals import GitHubAcquisitionError


class _Response:
    def __init__(self, ok: bool, payload: dict, status_code: int = 200):
        self.ok = ok
        self._payload = payload
        self.status_code = status_code

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


def test_branch_protection_404_is_valid_absence(mocker):
    mocker.patch(
        "scorers.security_ssdlc.logic.github_get",
        side_effect=[
            _Response(True, {"default_branch": "main"}),
            _Response(False, {"message": "Branch not protected"}, 404),
        ],
    )

    assert _has_branch_protection_required_checks("canonical/test-repo", "token") is False


@responses.activate
def test_branch_protection_permission_403_does_not_fall_back_to_anonymous_404():
    repo_url = "https://api.github.com/repos/canonical/test-repo"
    protection_url = f"{repo_url}/branches/main/protection"
    responses.add(
        responses.GET,
        repo_url,
        json={"default_branch": "main"},
        status=200,
    )
    responses.add(
        responses.GET,
        protection_url,
        json={"message": "Resource not accessible by integration"},
        status=403,
        headers={"X-RateLimit-Remaining": "999"},
    )
    responses.add(
        responses.GET,
        protection_url,
        json={"message": "Not Found"},
        status=404,
    )

    with pytest.raises(GitHubAcquisitionError) as exc_info:
        _has_branch_protection_required_checks("canonical/test-repo", "token")

    assert exc_info.value.status_code == 403
    assert len(responses.calls) == 2


def test_branch_protection_server_failure_raises(mocker):
    mocker.patch(
        "scorers.security_ssdlc.logic.github_get",
        side_effect=[
            _Response(True, {"default_branch": "main"}),
            _Response(False, {"message": "server error"}, 500),
        ],
    )

    with pytest.raises(GitHubAcquisitionError):
        _has_branch_protection_required_checks("canonical/test-repo", "token")


@pytest.mark.parametrize(
    "responses",
    [
        [_Response(True, {}), _Response(True, {})],
        [_Response(True, {"default_branch": "main"}), _Response(True, [])],
        [
            _Response(True, {"default_branch": "main"}),
            _Response(True, {"required_status_checks": {"contexts": "ci"}}),
        ],
    ],
)
def test_branch_protection_malformed_response_raises(mocker, responses):
    mocker.patch("scorers.security_ssdlc.logic.github_get", side_effect=responses)

    with pytest.raises(GitHubAcquisitionError):
        _has_branch_protection_required_checks("canonical/test-repo", "token")


def test_signed_commit_requirement_malformed_response_raises(mocker):
    mocker.patch(
        "scorers.security_ssdlc.logic.github_get",
        side_effect=[
            _Response(True, {"default_branch": "main"}),
            _Response(True, {"required_signatures": {"enabled": "false"}}),
        ],
    )

    with pytest.raises(GitHubAcquisitionError):
        _has_signed_commits_required("canonical/test-repo", "token")


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
        "renovate_enabled": True,
        "canonical_repo_automation_registered": True,
        "branch_protection_required_checks": True,
        "signed_commits_required": True,
        "sast_workflow_present": True,
        "cve_tracking_process_present": True,
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
        "renovate_enabled": False,
        "canonical_repo_automation_registered": False,
        "branch_protection_required_checks": False,
        "signed_commits_required": False,
        "sast_workflow_present": False,
        "cve_tracking_process_present": False,
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
    assert result["cve_tracking_process_present"] is True


def test_returns_defaults_when_repo_empty():
    result = compute_metrics(UNIT_EMPTY, "token")
    assert result == {
        "renovate_enabled": False,
        "canonical_repo_automation_registered": False,
        "branch_protection_required_checks": False,
        "signed_commits_required": False,
        "sast_workflow_present": False,
        "cve_tracking_process_present": False,
    }


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

    mocker.patch("scorers.security_ssdlc.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.security_ssdlc.logic.search_code_count", return_value=0)
    mocker.patch("scorers.security_ssdlc.logic.workflow_files", return_value=[])
    mocker.patch("scorers.security_ssdlc.logic.github_get", side_effect=fake_github_get)
    result = compute_metrics(UNIT, "token")
    assert result["signed_commits_required"] is True


def test_signed_commits_required_false_when_not_configured(mocker):
    """Signed commits should be False when not configured."""

    def fake_github_get(url, token, accept=None):
        if url.endswith("/repos/canonical/synapse-operator"):
            return _Response(True, {"default_branch": "main"})
        if url.endswith("/branches/main/protection"):
            return _Response(True, {"required_status_checks": {"contexts": ["ci"], "checks": []}})
        return _Response(False, {})

    mocker.patch("scorers.security_ssdlc.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.security_ssdlc.logic.search_code_count", return_value=0)
    mocker.patch("scorers.security_ssdlc.logic.workflow_files", return_value=[])
    mocker.patch("scorers.security_ssdlc.logic.github_get", side_effect=fake_github_get)
    result = compute_metrics(UNIT, "token")
    assert result["signed_commits_required"] is False
