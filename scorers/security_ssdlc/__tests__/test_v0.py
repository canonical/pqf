import base64
import json

import pytest
import responses

from engine.metric_outcomes import MetricState, measured
from engine.models import EvaluationUnit, ProductType
from scorers.security_ssdlc import logic
from scorers.shared.github_signals import GitHubAcquisitionError

API = "https://api.github.com/repos/canonical/test"
UNIT = EvaluationUnit(product_id="test", product_type=ProductType.CHARM, repo="canonical/test")
CONFIG_PATHS = (
    "renovate.json",
    "renovate.json5",
    ".github/renovate.json",
    ".github/renovate.json5",
    ".renovaterc",
    ".renovaterc.json",
    ".renovaterc.json5",
)


def run():
    scorer = getattr(logic, "compute_v0_metrics", None)
    assert scorer is not None, "V0 must expose a separately bound implementation"
    return scorer(UNIT, "token")


def evidence(
    config=None, protection=None, rulesets=None, branch="main", config_path="renovate.json"
):
    responses.get(API, json={"default_branch": branch})
    responses.get(
        f"{API}/issues?state=open&per_page=100&page=1",
        json=[dashboard()],
    )
    for path in CONFIG_PATHS:
        if config is not None and path == config_path:
            text = config if isinstance(config, str) else json.dumps(config)
            responses.get(
                f"{API}/contents/{path}",
                json={"encoding": "base64", "content": base64.b64encode(text.encode()).decode()},
            )
        else:
            responses.get(f"{API}/contents/{path}", status=404)
    branch_url = f"{API}/branches/{branch.replace('/', '%2F')}/protection"
    if protection is not None:
        protection = {"enforce_admins": {"enabled": True}, **protection}
    responses.get(
        branch_url,
        json=protection if protection is not None else {"message": "Branch not protected"},
        status=200 if protection is not None else 404,
    )
    responses.get(f"{branch_url}/required_signatures", status=404)
    responses.get(f"{API}/rulesets?includes_parents=true&per_page=100&page=1", json=rulesets or [])
    for ruleset in rulesets or []:
        ruleset_id = ruleset["id"]
        source = ruleset.get("source_type", "Repository")
        detail_url = (
            f"https://api.github.com/orgs/canonical/rulesets/{ruleset_id}"
            if source == "Organization"
            else f"{API}/rulesets/{ruleset_id}"
        )
        responses.get(detail_url, json=ruleset)


def dashboard():
    return {
        "title": "Dependency Dashboard",
        "state": "open",
        "user": {"login": "renovate[bot]", "type": "Bot", "id": 29139614},
        "updated_at": "2000-01-01T00:00:00Z",
    }


def rule(kind, *, enforcement="active", include=None, exclude=None, bypass=None, source=None):
    result = {
        "id": 7,
        "target": "branch",
        "enforcement": enforcement,
        "conditions": {
            "ref_name": {"include": include or ["~DEFAULT_BRANCH"], "exclude": exclude or []}
        },
        "rules": [
            {
                "type": kind,
                "parameters": {"required_status_checks": [{"context": "CI"}]},
            }
        ],
        "bypass_actors": bypass or [],
    }
    if source:
        result.update(source_type=source, source="canonical")
    return result


@responses.activate
def test_v0_measured_absence_has_exact_three_outputs():
    evidence()
    assert run() == {
        "renovate_enabled": measured(False),
        "branch_protection_required_checks": measured(False),
        "signed_commits_required": measured(False),
    }


@pytest.mark.parametrize("config", [{}, {"extends": ["config:base"]}, {"enabled": True}])
@responses.activate
def test_renovate_valid_onboarding_configuration(config):
    evidence(config=config)
    assert run()["renovate_enabled"] == measured(True)


@pytest.mark.parametrize("config", [{"enabled": False}, {"extends": [":disableRenovate"]}])
@responses.activate
def test_renovate_disabled_configuration_is_measured_false(config):
    evidence(config=config)
    assert run()["renovate_enabled"] == measured(False)


@pytest.mark.parametrize(
    "config",
    [
        '"renovate enabled"',
        "{broken",
        {"enabled": "true"},
        {"enabled": None},
        {"enabled": True, "extends": "config:base"},
    ],
)
@responses.activate
def test_renovate_invalid_configuration_is_not_evidence(config):
    evidence(config=config)
    assert run()["renovate_enabled"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_renovate_json5_comments_strings_and_trailing_commas():
    evidence(
        config="// onboarding\n{extends: ['config:base'], enabled: false,}",
        config_path="renovate.json5",
    )
    assert run()["renovate_enabled"] == measured(False)


@responses.activate
def test_renovate_resolves_canonical_preset_disabled():
    evidence(config={"extends": ["github>canonical/renovate-apps"]})
    responses.get(
        "https://api.github.com/repos/canonical/renovate-apps/contents/default.json",
        json={
            "encoding": "base64",
            "content": base64.b64encode(b'{"enabled": false}').decode(),
        },
    )
    assert run()["renovate_enabled"] == measured(False)


@responses.activate
def test_unknown_renovate_preset_is_not_assumed_enabled():
    evidence(config={"extends": ["github>untrusted/config"]})
    assert run()["renovate_enabled"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_classic_effective_protection_checks_and_signature_endpoint():
    evidence(protection={"required_status_checks": {"contexts": ["CI"]}})
    responses.replace(
        responses.GET,
        f"{API}/branches/main/protection/required_signatures",
        json={"enabled": True},
    )
    result = run()
    assert result["branch_protection_required_checks"] == measured(True)
    assert result["signed_commits_required"] == measured(True)


@pytest.mark.parametrize(
    "checks",
    [{"contexts": []}, {"contexts": [""]}, {"checks": []}, None],
)
@responses.activate
def test_classic_requires_a_nonempty_check(checks):
    evidence(protection={"required_status_checks": checks})
    assert run()["branch_protection_required_checks"] == measured(False)


@responses.activate
def test_classic_app_bound_check_counts():
    evidence(protection={"required_status_checks": {"checks": [{"context": "CI", "app_id": 1}]}})
    assert run()["branch_protection_required_checks"] == measured(True)


@pytest.mark.parametrize("kind", ["required_status_checks", "required_signatures"])
@pytest.mark.parametrize("source", ["Repository", "Organization"])
@responses.activate
def test_active_inherited_rulesets_apply_to_default_branch(kind, source):
    evidence(rulesets=[rule(kind, source=source)])
    key = (
        "signed_commits_required"
        if kind == "required_signatures"
        else "branch_protection_required_checks"
    )
    assert run()[key] == measured(True)


@pytest.mark.parametrize("enforcement", ["evaluate", "disabled"])
@responses.activate
def test_advisory_rulesets_do_not_count(enforcement):
    evidence(rulesets=[rule("required_signatures", enforcement=enforcement)])
    assert run()["signed_commits_required"] == measured(False)


@pytest.mark.parametrize(
    ("include", "exclude", "branch", "expected"),
    [
        (["refs/heads/release/*"], [], "release/1", True),
        (["refs/heads/*"], [], "release/1", False),
        (["refs/heads/**"], [], "release/1", True),
        (["~ALL"], ["~DEFAULT_BRANCH"], "main", False),
        (["~ALL"], ["refs/heads/main"], "main", False),
        (["refs/heads/work/*"], [], "main", False),
    ],
)
@responses.activate
def test_ruleset_patterns_and_exclusions(include, exclude, branch, expected):
    evidence(
        branch=branch,
        rulesets=[rule("required_signatures", include=include, exclude=exclude)],
    )
    assert run()["signed_commits_required"] == measured(expected)


@pytest.mark.parametrize("mode", ["always", "exempt", "pull_request"])
@responses.activate
def test_ruleset_bypass_actors_prevent_universal_requirement(mode):
    evidence(
        rulesets=[
            rule(
                "required_signatures",
                bypass=[{"actor_type": "Integration", "actor_id": 2740, "bypass_mode": mode}],
            )
        ]
    )
    assert run()["signed_commits_required"] == measured(False)


@responses.activate
def test_unknown_dynamic_rule_condition_is_insufficient_not_success():
    ruleset = rule("required_signatures")
    ruleset["conditions"]["ref_name"]["include"] = ["${dynamic.branch}"]
    evidence(rulesets=[ruleset])
    assert run()["signed_commits_required"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_unknown_ruleset_condition_does_not_count():
    ruleset = rule("required_signatures")
    ruleset["conditions"]["repository_property"] = {"include": [{"name": "quality"}]}
    evidence(rulesets=[ruleset])
    assert run()["signed_commits_required"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_stronger_independent_rule_can_resolve_unknown_rule():
    unknown = rule("required_signatures")
    unknown["id"] = 8
    unknown["conditions"]["unknown"] = True
    evidence(rulesets=[unknown, rule("required_signatures")])
    assert run()["signed_commits_required"] == measured(True)


@responses.activate
def test_ruleset_checks_require_nonempty_context():
    ruleset = rule("required_status_checks")
    ruleset["rules"][0]["parameters"]["required_status_checks"] = []
    evidence(rulesets=[ruleset])
    assert run()["branch_protection_required_checks"] == measured(False)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
@pytest.mark.parametrize(
    "path",
    [
        "",
        "/contents/renovate.json",
        "/branches/main/protection",
        "/rulesets?includes_parents=true&per_page=100&page=1",
    ],
)
@responses.activate
def test_required_api_failures_abort_not_false(status, path):
    evidence()
    responses.replace(responses.GET, f"{API}{path}", status=status)
    with pytest.raises(GitHubAcquisitionError):
        run()


def test_v0_missing_repo_is_not_applicable():
    scorer = getattr(logic, "compute_v0_metrics", None)
    assert scorer is not None
    unit = EvaluationUnit(product_id="test", product_type=ProductType.CHARM, repo="")
    assert all(
        outcome.state == MetricState.NOT_APPLICABLE for outcome in scorer(unit, "token").values()
    )


@responses.activate
def test_hidden_bypass_actors_are_not_assumed_absent():
    ruleset = rule("required_signatures")
    del ruleset["bypass_actors"]
    evidence(rulesets=[ruleset])
    assert run()["signed_commits_required"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_classic_admin_bypass_does_not_negate_configured_requirements():
    evidence(
        protection={
            "enforce_admins": {"enabled": False},
            "required_status_checks": {"contexts": ["CI"]},
            "required_signatures": {"enabled": True},
        }
    )
    result = run()
    assert result["branch_protection_required_checks"] == measured(True)
    assert result["signed_commits_required"] == measured(True)


@responses.activate
def test_classic_admin_policy_is_not_required_evidence():
    evidence(protection={})
    responses.replace(
        responses.GET,
        f"{API}/branches/main/protection",
        json={
            "required_status_checks": {"contexts": ["CI"]},
            "required_signatures": {"enabled": True},
        },
    )
    result = run()
    assert result["branch_protection_required_checks"] == measured(True)
    assert result["signed_commits_required"] == measured(True)


@responses.activate
def test_traefik_actual_renovate_onboarding_is_enabled():
    evidence(
        config={
            "$schema": "https://docs.renovatebot.com/renovate-schema.json",
            "extends": ["config:recommended", "group:allNonMajor"],
            "customDatasources": {
                "charmhub": {
                    "defaultRegistryUrlTemplate": "https://api.charmhub.io/v2/charms/info/{{packageName}}?fields=channel-map",
                    "format": "json",
                    "transformTemplates": [
                        '{"releases": [{"version": $string($$.(`channel-map`['
                        "channel.risk = 'edge' and channel.track = 'latest' and "
                        "channel.base.architecture = 'amd64' and channel.base.channel = "
                        "'24.04'].revision.revision))}]}"
                    ],
                }
            },
            "customManagers": [
                {
                    "customType": "regex",
                    "datasourceTemplate": "docker",
                    "managerFilePatterns": ["/(^|/)rockcraft.yaml$/"],
                    "matchStrings": [
                        "# renovate: base:\\s+(?<depName>[^:]*):(?<currentValue>[^\\s@]*)"
                    ],
                    "versioningTemplate": "ubuntu",
                },
                {
                    "customType": "regex",
                    "datasourceTemplate": "custom.charmhub",
                    "fileMatch": ["\\.tftest\\.hcl$", "\\.tf$"],
                    "matchStrings": [
                        '# renovate: depName="(?<packageName>[^"]+)"\\s*\\n\\s*'
                        "(?<fieldName>[a-zA-Z0-9_]+)\\s*=\\s*(?<currentValue>\\d+)"
                    ],
                    "versioningTemplate": "semver-coerced",
                },
            ],
            "packageRules": [
                {"enabled": True, "matchDatasources": ["docker"], "pinDigests": True},
                {"enabled": True, "matchDatasources": ["custom.charmhub"], "automerge": True},
                {
                    "enabled": False,
                    "matchFileNames": ["rockcraft.yaml"],
                    "matchUpdateTypes": ["major", "minor", "patch"],
                },
                {
                    "groupName": "charm-ci",
                    "matchPackageNames": ["opcli", "canonical/charm-ci", "*charm-ci*"],
                },
            ],
            "ignorePaths": [],
            "schedule": ["* * * * 0,6"],
            "automerge": True,
            "vulnerabilityAlerts": {"enabled": True},
        }
    )
    assert run()["renovate_enabled"] == measured(True)


@responses.activate
def test_unrelated_config_options_are_not_onboarding_conformance_gates():
    evidence(config={"customDatasources": {}, "futureValidRenovateOption": {"value": True}})
    assert run()["renovate_enabled"] == measured(True)


@responses.activate
def test_all_packages_disabled_is_measured_false():
    evidence(config={"packageRules": [{"matchPackageNames": ["*"], "enabled": False}]})
    assert run()["renovate_enabled"] == measured(False)


@responses.activate
def test_selective_reenable_after_disable_all_is_enabled():
    evidence(
        config={
            "packageRules": [
                {"matchPackageNames": ["*"], "enabled": False},
                {"matchDatasources": ["docker"], "enabled": True},
            ]
        }
    )
    assert run()["renovate_enabled"] == measured(True)


@responses.activate
def test_unknown_rule_type_is_insufficient():
    ruleset = rule("required_signatures")
    ruleset["rules"] = [{"type": "${dynamic.rule}"}]
    evidence(rulesets=[ruleset])
    assert run()["signed_commits_required"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_missing_ruleset_check_parameters_is_insufficient():
    ruleset = rule("required_status_checks")
    del ruleset["rules"][0]["parameters"]
    evidence(rulesets=[ruleset])
    assert run()["branch_protection_required_checks"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_inherited_empty_preset_does_not_override_disabled_enabled_setting():
    evidence(config={"extends": [":disableRenovate", "github>canonical/renovate-apps"]})
    responses.get(
        "https://api.github.com/repos/canonical/renovate-apps/contents/default.json",
        json={"encoding": "base64", "content": base64.b64encode(b"{}").decode()},
    )
    assert run()["renovate_enabled"] == measured(False)


@responses.activate
def test_renovate_unknown_preset_is_unknown_even_with_enabled_true():
    evidence(config={"enabled": True, "extends": ["github>untrusted/config"]})
    assert run()["renovate_enabled"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_supported_json5_comments_can_separate_keys_from_values():
    evidence(config="{enabled /* note */ : false}", config_path="renovate.json5")
    assert run()["renovate_enabled"] == measured(False)


@responses.activate
def test_rulesets_are_paginated_without_silently_ignoring_later_requirements():
    evidence()
    inactive = [rule("required_signatures", enforcement="disabled") for _ in range(100)]
    responses.replace(
        responses.GET,
        f"{API}/rulesets?includes_parents=true&per_page=100&page=1",
        json=inactive,
    )
    responses.get(f"{API}/rulesets/7", json=inactive[0])
    active = rule("required_signatures")
    active["id"] = 8
    responses.get(
        f"{API}/rulesets?includes_parents=true&per_page=100&page=2",
        json=[active],
    )
    responses.get(f"{API}/rulesets/8", json=active)
    assert run()["signed_commits_required"] == measured(True)


@responses.activate
def test_classic_requirements_do_not_mask_failure_to_acquire_inherited_rules():
    evidence(
        protection={
            "required_status_checks": {"contexts": ["CI"]},
            "required_signatures": {"enabled": True},
        }
    )
    responses.replace(
        responses.GET,
        f"{API}/rulesets?includes_parents=true&per_page=100&page=1",
        status=500,
    )
    with pytest.raises(GitHubAcquisitionError):
        run()


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
@responses.activate
def test_required_signature_endpoint_errors_abort(status):
    evidence(protection={})
    responses.replace(
        responses.GET,
        f"{API}/branches/main/protection/required_signatures",
        status=status,
    )
    with pytest.raises(GitHubAcquisitionError):
        run()


@responses.activate
def test_org_ruleset_repository_name_exclusion_applies():
    ruleset = rule("required_signatures", source="Organization")
    ruleset["conditions"]["repository_name"] = {"include": ["~ALL"], "exclude": ["test"]}
    evidence(rulesets=[ruleset])
    assert run()["signed_commits_required"] == measured(False)


@responses.activate
def test_org_ruleset_literal_repository_ids_apply():
    ruleset = rule("required_signatures", source="Organization")
    ruleset["conditions"]["repository_id"] = {"repository_ids": [123]}
    evidence(rulesets=[ruleset])
    responses.replace(responses.GET, API, json={"default_branch": "main", "id": 123})
    assert run()["signed_commits_required"] == measured(True)


@responses.activate
def test_cyclic_canonical_presets_are_insufficient():
    evidence(config={"extends": ["github>canonical/renovate-apps"]})
    config = json.dumps({"extends": ["github>canonical/renovate-apps"]})
    responses.get(
        "https://api.github.com/repos/canonical/renovate-apps/contents/default.json",
        json={"encoding": "base64", "content": base64.b64encode(config.encode()).decode()},
    )
    assert run()["renovate_enabled"].state == MetricState.INSUFFICIENT_DATA


@pytest.mark.parametrize(
    "issues",
    [
        [],
        [{**dashboard(), "state": "closed"}],
        [{**dashboard(), "pull_request": {"url": "https://api.github.com/pulls/1"}}],
        [{**dashboard(), "user": {"login": "human", "type": "User", "id": 123}}],
        [{**dashboard(), "user": {"login": "renovate[bot]", "type": "User", "id": 29139614}}],
        [{**dashboard(), "user": {"login": "renovate[bot]", "type": "Bot", "id": 123}}],
        [{**dashboard(), "title": "Not the Dependency Dashboard"}],
    ],
)
@responses.activate
def test_renovate_requires_open_genuine_bot_dashboard(issues):
    evidence(config={})
    responses.replace(responses.GET, f"{API}/issues?state=open&per_page=100&page=1", json=issues)
    assert run()["renovate_enabled"] == measured(False)


@responses.activate
def test_renovate_dashboard_on_later_page_counts_without_recency_gate():
    evidence(config={})
    unrelated = [{**dashboard(), "title": "Unrelated issue"} for _ in range(100)]
    responses.replace(responses.GET, f"{API}/issues?state=open&per_page=100&page=1", json=unrelated)
    responses.get(f"{API}/issues?state=open&per_page=100&page=2", json=[dashboard()])
    assert run()["renovate_enabled"] == measured(True)
    assert any("page=2" in call.request.url for call in responses.calls)


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
@responses.activate
def test_renovate_dashboard_acquisition_errors_fail_closed(status):
    evidence(config={})
    responses.replace(responses.GET, f"{API}/issues?state=open&per_page=100&page=1", status=status)
    with pytest.raises(GitHubAcquisitionError):
        run()


@responses.activate
def test_disabled_config_stays_false_despite_open_bot_dashboard():
    evidence(config={"enabled": False})
    assert run()["renovate_enabled"] == measured(False)


@responses.activate
def test_invalid_config_stays_insufficient_despite_open_bot_dashboard():
    evidence(config="{broken")
    assert run()["renovate_enabled"].state == MetricState.INSUFFICIENT_DATA


@pytest.mark.parametrize("payload", [{}, [None]])
@responses.activate
def test_uninterpretable_dashboard_evidence_is_insufficient(payload):
    evidence(config={})
    responses.replace(responses.GET, f"{API}/issues?state=open&per_page=100&page=1", json=payload)
    assert run()["renovate_enabled"].state == MetricState.INSUFFICIENT_DATA
