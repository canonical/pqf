import yaml

from engine.models import EvaluationUnit, ProductType
from scorers.security_ssdlc.logic import (
    _has_branch_protection_required_checks,
    _is_registered_in_repo_automation,
    compute_metrics,
)


class _Response:
    def __init__(self, ok: bool, payload: dict):
        self.ok = ok
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
    registration_path = (
        "groups/is/platform-engineering/repos/saml-integrator-operator/inputs.hcl"
    )
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
            _Response(True, {"default_branch": "main"}),
            _Response(True, {"required_status_checks": {"contexts": ["ci"], "checks": []}}),
        ],
    )

    result = compute_metrics(UNIT, "token")
    assert result == {
        "renovate_enabled": True,
        "canonical_repo_automation_registered": True,
        "branch_protection_required_checks": True,
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
            _Response(True, {"default_branch": "main"}),
            _Response(True, {"required_status_checks": {}}),
        ],
    )
    result = compute_metrics(UNIT, "token")
    assert result == {
        "renovate_enabled": False,
        "canonical_repo_automation_registered": False,
        "branch_protection_required_checks": False,
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
        "sast_workflow_present": False,
        "cve_tracking_process_present": False,
    }


def test_dimensions_yaml_mentions_new_ssdlc_metrics():
    from pathlib import Path

    data = yaml.safe_load(Path("config/dimensions.yaml").read_text())
    outputs = data["dimensions"]["security_ssdlc"]["outputs"]
    assert "renovate_enabled" in outputs
    assert "canonical_repo_automation_registered" in outputs
    assert "sast_workflow_present" in outputs
    assert "cve_tracking_process_present" in outputs
