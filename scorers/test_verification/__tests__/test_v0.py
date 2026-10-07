import base64

import pytest
import responses

from engine.metric_outcomes import MetricState, measured
from engine.models import EvaluationUnit, ProductType
from scorers.test_verification.v0 import evaluate_checks, evaluate_files

UNIT = EvaluationUnit("example", ProductType.CHARM, "canonical/example", subpath="charm")


def files(extra=None):
    return {
        "charm/charmcraft.yaml": "name: example\ncontainers:\n  app: {}\n",
        **(extra or {}),
    }


def workflow(body):
    return {"jobs": body}


def spread(concierge="concierge.yaml"):
    return f"""
backends:
  integration-test:
    type: integration-test
integration-suites:
  tests/integration/:
    backends: [integration-test]
    environment:
      CONCIERGE: {concierge}
"""


def test_empty_tests_do_not_adopt_jubilant_or_unit_runners():
    result = evaluate_files(UNIT, files())
    assert result["uses_ops_testing"] == measured(False)
    assert result["uses_jubilant"] == measured(False)
    assert result["uses_gh_runners_unit_testing"] == measured(False)
    assert result["uses_tf_v1_provider"].state == MetricState.NOT_APPLICABLE


@pytest.mark.parametrize(
    "source",
    ["import jubilant as j", "from jubilant import Juju", "from jubilant.foo import thing"],
)
def test_jubilant_accepts_valid_imports_only_in_component_integration_tests(source):
    result = evaluate_files(UNIT, files({"charm/tests/integration/test_app.py": source}))
    assert result["uses_jubilant"] == measured(True)
    result = evaluate_files(
        UNIT,
        files(
            {
                "other/tests/integration/test_app.py": source,
                "charm/tests/unit/test_app.py": source,
                "charm/README.md": source,
            }
        ),
    )
    assert result["uses_jubilant"] == measured(False)


@pytest.mark.parametrize(
    "source",
    [
        "from ops.testing import Harness as H",
        "import ops.testing as testing\nh = testing.Harness(None)",
        "import ops\nh = ops.testing.Harness(None)",
        "from ops import testing\nh = testing.Harness(None)",
    ],
)
def test_harness_ast_references_are_deprecated(source):
    result = evaluate_files(UNIT, files({"charm/tests/unit/test_app.py": source}))
    assert result["uses_ops_testing"] == measured(False)


def test_harness_mentions_and_other_component_do_not_fail():
    result = evaluate_files(
        UNIT,
        files(
            {
                "charm/tests/unit/test_app.py": "from ops.testing import Context\n"
                '# Harness\ntext = "Harness"\n',
                "other/tests/test_app.py": "from ops.testing import Harness",
            }
        ),
    )
    assert result["uses_ops_testing"] == measured(True)


@pytest.mark.parametrize(
    "source",
    [
        "import ops.testing",
        "import ops.testing as testing",
        "from ops import testing",
        "from ops.testing import Context",
    ],
)
def test_ops_testing_requires_positive_scoped_import(source):
    assert evaluate_files(
        UNIT,
        files(
            {
                "charm/tests/unit/test_app.py": source,
            }
        ),
    )["uses_ops_testing"] == measured(True)
    assert evaluate_files(
        UNIT,
        files(
            {
                "charm/tests/unit/test_app.py": 'text = "ops.testing"\n',
                "other/tests/unit/test_app.py": source,
            }
        ),
    )["uses_ops_testing"] == measured(False)


def test_parse_errors_are_insufficient():
    result = evaluate_files(UNIT, files({"charm/tests/integration/test_app.py": "import ("}))
    assert result["uses_jubilant"].state == MetricState.INSUFFICIENT_DATA


def test_integration_context_does_not_satisfy_ops_unit_testing():
    result = evaluate_files(
        UNIT, files({"charm/tests/integration/test_app.py": "from ops.testing import Context"})
    )
    assert result["uses_ops_testing"] == measured(False)


def test_integration_harness_does_not_fail_ops_unit_testing():
    result = evaluate_files(
        UNIT,
        files(
            {
                "charm/tests/unit/test_app.py": "from ops.testing import Context",
                "charm/tests/integration/test_app.py": (
                    "from ops.testing import Harness\nimport jubilant"
                ),
            }
        ),
    )
    assert result["uses_ops_testing"] == measured(True)
    assert result["uses_jubilant"] == measured(True)


def test_invalid_integration_python_does_not_make_ops_unit_testing_unknown():
    result = evaluate_files(
        UNIT,
        files(
            {
                "charm/tests/unit/test_app.py": "from ops.testing import Context",
                "charm/tests/integration/test_app.py": "import (",
            }
        ),
    )
    assert result["uses_ops_testing"] == measured(True)
    assert result["uses_jubilant"].state == MetricState.INSUFFICIENT_DATA


@pytest.mark.parametrize(
    "declaration",
    [
        'juju = { version = "~> 1.0" }',
        'juju = "~> 1.0"',
        'juju = { source = "hashicorp/juju" version = "~> 1.0" }',
    ],
)
def test_terraform_implicit_or_wrong_juju_source_is_noncompliant(declaration):
    result = evaluate_files(
        UNIT,
        files({"charm/versions.tf": f"terraform {{ required_providers {{ {declaration} }} }}"}),
    )
    assert result["uses_tf_v1_provider"] == measured(False)


@pytest.mark.parametrize("source", ["juju/juju", "registry.terraform.io/juju/juju"])
def test_terraform_arbitrary_local_alias_requires_recognized_source(source):
    result = evaluate_files(
        UNIT,
        files(
            {
                "charm/versions.tf.json": '{"terraform":{"required_providers":{"controller":'
                f'{{"source":"{source}","version":"~> 1.0"}}' + "}}}",
            }
        ),
    )
    assert result["uses_tf_v1_provider"] == measured(True)


def test_workflows_and_linked_concierge_are_component_scoped():
    source = files(
        {
            ".github/workflows/test.yaml": """
jobs:
  integration:
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@v1.0.0
    with:
      working-directory: charm
  unit:
    uses: canonical/operator-workflows/.github/workflows/test.yaml@main
    with:
      working-directory: charm
""",
            "charm/spread.yaml": """
backends:
  integration-test:
    type: integration-test
integration-suites:
  tests/integration/:
    backends: [integration-test]
    environment:
      CONCIERGE: concierge.yaml
""",
            "charm/concierge.yaml": "juju:\n  channel: 4/stable\nproviders:\n  k8s: {}\n",
            "other/concierge.yaml": "juju:\n  channel: 3.6/stable\n",
        }
    )
    result = evaluate_files(UNIT, source)
    assert result["uses_charm_ci"] == measured(True)
    assert result["uses_gh_runners_unit_testing"] == measured(True)
    assert result["supports_canonical_k8s"] == measured(True)
    assert result["supports_juju_4"] == measured(True)
    assert result["supports_juju_lts"] == measured(False)


def test_unused_concierge_and_incidental_mentions_do_not_count():
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/test.yaml": """
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo canonical/charm-ci/.github/workflows/integration-test.yml
""",
                "charm/concierge.yaml": "juju:\n  channel: 4/stable\nproviders:\n  k8s: {}\n",
            }
        ),
    )
    for key in ("uses_charm_ci", "supports_juju_4", "supports_canonical_k8s"):
        assert result[key] == measured(False)


@pytest.mark.parametrize(
    ("runner", "state", "value"),
    [
        ("ubuntu-24.04", MetricState.MEASURED, True),
        ("[self-hosted, linux]", MetricState.MEASURED, False),
        ("${{ inputs.runner }}", MetricState.INSUFFICIENT_DATA, None),
    ],
)
def test_local_unit_jobs_require_real_runner_evidence(runner, state, value):
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/unit.yml": f"""
jobs:
  unit:
    runs-on: {runner}
    defaults:
      run:
        working-directory: charm
    steps:
      - run: tox -e unit
"""
            }
        ),
    )["uses_gh_runners_unit_testing"]
    assert (result.state, result.value) == (state, value)


@pytest.mark.parametrize("track", ["4/edge", "4.1/stable", "3/stable", "4/stable/foo"])
def test_exact_juju_track_is_required(track):
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/integration.yml": """
jobs:
  integration:
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@main
    with:
      working-directory: charm
""",
                "charm/spread.yaml": spread(),
                "charm/concierge.yaml": f"juju:\n  channel: {track}",
            }
        ),
    )
    assert result["supports_juju_4"] == measured(False)


def test_snaps_all_charm_checks_not_applicable():
    result = evaluate_files(EvaluationUnit("snap", ProductType.SNAP, "a/b"), {})
    assert len(result) == 8
    assert all(outcome.state == MetricState.NOT_APPLICABLE for outcome in result.values())


def test_machine_k8s_is_not_applicable():
    result = evaluate_files(UNIT, {"charm/charmcraft.yaml": "name: example\n"})
    assert result["supports_canonical_k8s"].state == MetricState.NOT_APPLICABLE


@pytest.mark.parametrize("constraint", ["~> 1.0", "~> 1.2.3", ">= 1.0, < 2.0", "= 1.2.3"])
def test_terraform_supported_major_one_constraints(constraint):
    result = evaluate_files(
        UNIT,
        files(
            {
                "charm/terraform/versions.tf": f"""
terraform {{
  required_providers {{
    juju = {{ source = "juju/juju", version = "{constraint}" }}
  }}
}}
"""
            }
        ),
    )
    assert result["uses_tf_v1_provider"] == measured(True)


def test_terraform_all_modules_must_use_v1():
    result = evaluate_files(
        UNIT,
        files(
            {
                "charm/a/versions.tf.json": '{"terraform":{"required_providers":{"juju":'
                '{"source":"juju/juju","version":"~> 1.0"}}}}',
                "charm/b/versions.tf": "terraform { required_providers { juju = "
                '{ source = "juju/juju" version = "~> 0.20" } } }',
            }
        ),
    )
    assert result["uses_tf_v1_provider"] == measured(False)


def check(name, conclusion="success", *, id=1, status="completed"):
    return {"name": name, "conclusion": conclusion, "id": id, "status": status, "app": {"id": 1}}


def test_ci_does_not_ignore_failed_jobs_or_pending_reruns():
    assert evaluate_checks([check("unit"), check("integration", "failure")]) == measured(False)
    pending = check("unit", None, id=2, status="in_progress")
    assert evaluate_checks([check("unit"), pending]).state == MetricState.INSUFFICIENT_DATA
    assert evaluate_checks([check("unit", "failure"), check("unit", id=2)]) == measured(True)
    assert evaluate_checks([check("unit")], required={"integration"}).state == (
        MetricState.INSUFFICIENT_DATA
    )


def test_other_component_root_workflow_does_not_prove_component_juju():
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/integration.yml": """
jobs:
  integration:
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@main
    with:
      juju-channel: 4/stable
      concierge-config: concierge.yaml
""",
                "concierge.yaml": "juju:\n  channel: 4/stable\nproviders:\n  k8s: {}\n",
            }
        ),
    )
    assert result["uses_charm_ci"] == measured(False)
    assert result["supports_juju_4"] == measured(False)
    assert result["supports_canonical_k8s"] == measured(False)


def test_nested_charm_tests_do_not_satisfy_root_charm():
    unit = EvaluationUnit("root", ProductType.CHARM, "a/b")
    result = evaluate_files(
        unit,
        {
            "charmcraft.yaml": "name: root",
            "child/charmcraft.yaml": "name: child",
            "child/tests/integration/test_app.py": "import jubilant",
            "child/tests/unit/test_app.py": "from ops.testing import Harness",
        },
    )
    assert result["uses_jubilant"] == measured(False)
    assert result["uses_ops_testing"] == measured(False)


def test_literal_matrix_expansion_and_disabled_provider():
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/test.yml": """
jobs:
  integration:
    strategy:
      matrix:
        component: [charm, other]
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@main
    with:
      working-directory: ${{ matrix.component }}
""",
                "charm/spread.yaml": spread()
                + """
      CONCIERGE/lts: concierge-lts.yaml
""",
                "charm/concierge.yaml": (
                    "juju:\n  channel: 4/stable\nproviders:\n  k8s:\n    enable: false\n"
                ),
                "charm/concierge-lts.yaml": "juju:\n  channel: 3.6/stable",
            }
        ),
    )
    assert result["supports_juju_4"] == measured(True)
    assert result["supports_juju_lts"] == measured(True)
    assert result["supports_canonical_k8s"] == measured(False)


def test_terraform_uninterpretable_constraint_is_insufficient_not_false():
    result = evaluate_files(
        UNIT,
        files(
            {
                "charm/main.tf": "terraform { required_providers { juju = { "
                'source = "juju/juju" version = var.juju_version } } }',
            }
        ),
    )
    assert result["uses_tf_v1_provider"].state == MetricState.INSUFFICIENT_DATA


def test_nested_kubernetes_assumption_is_not_machine():
    result = evaluate_files(
        UNIT,
        {
            "charm/charmcraft.yaml": "name: example\nassumes:\n  - any-of:\n      - k8s-api\n",
        },
    )
    assert result["supports_canonical_k8s"] == measured(False)


def test_unsupported_charm_ci_inputs_are_not_linked_configuration():
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/test.yml": """
jobs:
  integration:
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@v1.0.0
    with:
      working-directory: charm
      juju-channel: 4/stable
      concierge-config: concierge.yaml
""",
                "charm/concierge.yaml": "juju: {channel: 4/stable}\nproviders: {k8s: {}}",
            }
        ),
    )
    assert result["supports_juju_4"] == measured(False)
    assert result["supports_canonical_k8s"] == measured(False)


def test_missing_repository_is_insufficient_not_adoption():
    from scorers.test_verification.logic import compute_v0_metrics

    result = compute_v0_metrics(EvaluationUnit("unknown", ProductType.CHARM, ""))
    assert all(outcome.state == MetricState.INSUFFICIENT_DATA for outcome in result.values())


def test_root_spread_suite_can_link_component_configuration():
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/integration.yml": """
jobs:
  integration:
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@main
""",
                "spread.yaml": """
backends:
  integration-test: {type: integration-test}
integration-suites:
  charm/tests/integration/:
    working-dir: charm
    backends: [integration-test]
    environment:
      CONCIERGE: environments/k8s.yaml
  other/tests/integration/:
    working-dir: other
    backends: [integration-test]
    environment:
      CONCIERGE: environments/juju4.yaml
""",
                "environments/k8s.yaml": "providers:\n  k8s: {}\njuju:\n  channel: 3.6/stable",
                "environments/juju4.yaml": "juju:\n  channel: 4/stable",
            }
        ),
    )
    assert result["uses_charm_ci"] == measured(True)
    assert result["supports_canonical_k8s"] == measured(True)
    assert result["supports_juju_lts"] == measured(True)
    assert result["supports_juju_4"] == measured(False)


def test_known_charm_ci_call_still_adopted_when_spread_is_unparseable():
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/integration.yml": """
jobs:
  integration:
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@main
    with:
      working-directory: charm
""",
                "charm/spread.yaml": "[not yaml",
            }
        ),
    )
    assert result["uses_charm_ci"] == measured(True)
    assert result["supports_juju_4"].state == MetricState.INSUFFICIENT_DATA


def test_non_unit_workflow_dynamic_runner_does_not_count_as_unit():
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/build.yml": """
jobs:
  build:
    runs-on: ${{ inputs.runner }}
    steps:
      - run: make build
""",
            }
        ),
    )
    assert result["uses_gh_runners_unit_testing"] == measured(False)


@pytest.mark.parametrize(
    "command",
    [
        "uv run tox -e unit",
        "uv run pytest tests/unit",
        "python -m pytest tests/unit",
        "python3 -m tox -e unit",
    ],
)
def test_local_unit_standard_command_wrappers(command):
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/test.yml": f"""
jobs:
  unit:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: charm
    steps:
      - run: {command}
""",
            }
        ),
    )
    assert result["uses_gh_runners_unit_testing"] == measured(True)


def test_operator_unit_directory_not_charm_directory_controls_scope():
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/test.yml": """
jobs:
  unit:
    uses: canonical/operator-workflows/.github/workflows/test.yaml@main
    with:
      charm-directory: charm
""",
            }
        ),
    )
    assert result["uses_gh_runners_unit_testing"] == measured(False)


def test_terraform_alias_lists_do_not_hide_literal_juju_requirement():
    result = evaluate_files(
        UNIT,
        files(
            {
                "charm/versions.tf": """
terraform {
  required_providers {
    controller = {
      source = "juju/juju"
      version = "~> 1.0"
      configuration_aliases = [juju.alias]
    }
  }
}
resource "juju_model" "model" { count = 1 + 2 }
""",
            }
        ),
    )
    assert result["uses_tf_v1_provider"] == measured(True)


def test_ci_checks_are_deduplicated_by_app_not_just_name():
    passing = check("unit", id=2)
    failing = check("unit", "failure")
    failing["app"] = {"id": 2}
    assert evaluate_checks([passing, failing]) == measured(False)


def test_ci_statuses_are_latest_per_context():
    assert evaluate_checks(
        [],
        statuses=[
            {"context": "unit", "state": "failure", "id": 1},
            {"context": "unit", "state": "success", "id": 2},
        ],
    ) == measured(True)
    assert (
        evaluate_checks(
            [check("unit")],
            statuses=[
                {"context": "integration", "state": "pending", "id": 1},
            ],
        ).state
        == MetricState.INSUFFICIENT_DATA
    )


def github_snapshot(*, charm=True, tracks=("latest",), tip_checks=None, associated=None):
    base = "https://api.github.com/repos/canonical/example"
    responses.get(base, json={"default_branch": "main"})
    responses.get(base + "/branches/main", json={"commit": {"sha": "tip"}})
    source = "name: example\ncontainers:\n  app: {}\n"
    tree = [{"type": "blob", "path": "charm/charmcraft.yaml", "sha": "config"}] if charm else []
    responses.get(base + "/git/trees/tip", json={"tree": tree, "truncated": False})
    if charm:
        responses.get(
            base + "/git/blobs/config",
            json={
                "encoding": "base64",
                "content": base64.b64encode(source.encode()).decode(),
            },
        )
        responses.get(
            "https://api.charmhub.io/v2/charms/info/example",
            json={"channel-map": [{"channel": {"track": track}} for track in tracks]},
        )
    responses.get(base + "/rules/branches/main", json=[])
    responses.get(base + "/commits/tip/check-runs", json={"check_runs": tip_checks or []})
    responses.get(base + "/commits/tip/statuses", json=[])
    if not tip_checks:
        responses.get(base + "/commits/tip/pulls", json=associated or [])
    return base


@responses.activate
def test_runner_checks_default_and_all_published_tracks():
    from scorers.test_verification.logic import compute_v0_metrics

    base = github_snapshot(tracks=("latest", "1", "2"), tip_checks=[check("test")])
    for track, conclusion in [("1", "success"), ("2", "failure")]:
        responses.get(base + f"/branches/track%2F{track}", json={"commit": {"sha": track}})
        responses.get(base + f"/rules/branches/track%2F{track}", json=[])
        responses.get(
            base + f"/commits/{track}/check-runs",
            json={
                "check_runs": [check("test", conclusion)],
            },
        )
        responses.get(base + f"/commits/{track}/statuses", json=[])
    result = compute_v0_metrics(UNIT)
    assert result["ci_passing"] == measured(False)
    assert len(result) == 9
    assert all(isinstance(value, type(measured(True))) for value in result.values())


@responses.activate
def test_allure_success_is_not_used_for_ci():
    from dataclasses import replace

    from scorers.test_verification.logic import compute_v0_metrics

    github_snapshot(tip_checks=[check("unit", "failure")])
    unit = replace(UNIT, allure_report_url="https://example.com/_latest")
    assert compute_v0_metrics(unit)["ci_passing"] == measured(False)
    assert not any("example.com" in call.request.url for call in responses.calls)


@responses.activate
def test_arbitrary_linked_config_is_acquired_and_api_failure_propagates():
    from scorers.test_verification.logic import compute_v0_metrics

    base = github_snapshot(tip_checks=[check("unit")])
    contents = {
        "charm/charmcraft.yaml": "name: example\ncontainers: {app: {}}",
        ".github/workflows/test.yml": """
jobs:
  integration:
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@main
    with:
      working-directory: charm
""",
        "charm/spread.yaml": spread("env/custom.yaml"),
        "charm/env/custom.yaml": "juju: {channel: 4/stable}\nproviders: {k8s: {}}",
    }
    responses.replace(
        responses.GET,
        base + "/git/trees/tip",
        json={
            "tree": [
                {"type": "blob", "path": path, "sha": f"blob-{i}"}
                for i, path in enumerate(contents)
            ],
            "truncated": False,
        },
    )
    for i, text in enumerate(contents.values()):
        responses.get(
            base + f"/git/blobs/blob-{i}",
            json={
                "encoding": "base64",
                "content": base64.b64encode(text.encode()).decode(),
            },
        )
    assert compute_v0_metrics(UNIT)["supports_juju_4"] == measured(True)
    responses.replace(responses.GET, base + "/git/blobs/blob-3", status=503)
    with pytest.raises(Exception, match="503"):
        compute_v0_metrics(UNIT)


@responses.activate
def test_snaps_do_not_call_charmhub():
    from scorers.test_verification.logic import compute_v0_metrics

    github_snapshot(charm=False, tip_checks=[check("test")])
    result = compute_v0_metrics(EvaluationUnit("example", ProductType.SNAP, "canonical/example"))
    assert result["ci_passing"] == measured(True)
    assert all(
        result[key].state == MetricState.NOT_APPLICABLE for key in result if key != "ci_passing"
    )


@pytest.mark.parametrize("merge_sha,base_branch", [("old-tip", "main"), ("tip", "other")])
@responses.activate
def test_ci_rejects_wrong_merged_pr_association(merge_sha, base_branch):
    from scorers.test_verification.logic import compute_v0_metrics

    github_snapshot(
        associated=[
            {
                "merged_at": "2026-01-01",
                "merge_commit_sha": merge_sha,
                "base": {"ref": base_branch, "repo": {"full_name": "canonical/example"}},
                "head": {"sha": "pr-head"},
            }
        ]
    )
    assert compute_v0_metrics(UNIT)["ci_passing"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_ci_uses_exact_merged_pr_head_when_tip_has_no_checks():
    from scorers.test_verification.logic import compute_v0_metrics

    base = github_snapshot(
        associated=[
            {
                "merged_at": "2026-01-01",
                "merge_commit_sha": "tip",
                "base": {"ref": "main", "repo": {"full_name": "canonical/example"}},
                "head": {"sha": "tip"},
            }
        ]
    )
    responses.get(base + "/commits/tip/check-runs", json={"check_runs": [check("test")]})
    responses.get(base + "/commits/tip/statuses", json=[])
    assert compute_v0_metrics(UNIT)["ci_passing"] == measured(True)


@responses.activate
def test_traefik_issue_42_squash_pr_checks_do_not_prove_current_branch_commit():
    from scorers.test_verification.logic import compute_v0_metrics

    github_snapshot(
        associated=[
            {
                "merged_at": "2026-01-01",
                "merge_commit_sha": "tip",
                "base": {"ref": "main", "repo": {"full_name": "canonical/example"}},
                "head": {"sha": "tested-before-squash"},
            }
        ]
    )
    assert compute_v0_metrics(UNIT)["ci_passing"].state == MetricState.INSUFFICIENT_DATA


def test_traefik_issue_42_linked_concierge_and_exact_configured_tracks():
    unit = EvaluationUnit("traefik", ProductType.CHARM, "canonical/traefik-k8s-operator")
    result = evaluate_files(
        unit,
        {
            "charmcraft.yaml": "name: traefik-k8s\ncontainers: {traefik: {}}",
            ".github/workflows/integration-test.yaml": """
jobs:
  integration-test:
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@v1.0.0
""",
            "spread.yaml": """
backends:
  integration-test: {type: integration-test}
environment:
  CONCIERGE: '$(HOST: echo "${CONCIERGE:-concierge-juju3.yaml}")'
integration-suites:
  tests/integration/:
    working-dir: ./
    backends: [integration-test]
  tests/integration/juju4/:
    working-dir: ./
    backends: [integration-test]
    environment:
      CONCIERGE: concierge-juju4.yaml
""",
            "concierge-juju3.yaml": "juju: {channel: 3.6/stable}\nproviders: {k8s: {}}",
            "concierge-juju4.yaml": "juju: {channel: 4.0/stable}\nproviders: {k8s: {}}",
        },
    )
    assert result["uses_charm_ci"] == measured(True)
    assert result["supports_juju_lts"] == measured(True)
    assert result["supports_canonical_k8s"] == measured(True)
    assert result["supports_juju_4"] == measured(False)


def test_machine_and_k8s_siblings_keep_metadata_and_test_configuration_scoped():
    source = {
        "machine/charmcraft.yaml": "name: machine",
        "k8s/charmcraft.yaml": "name: k8s\ncontainers: {app: {}}",
        "k8s/tests/unit/test_app.py": "from ops.testing import Context",
        "k8s/tests/integration/test_app.py": "import jubilant",
        ".github/workflows/integration.yml": """
jobs:
  integration:
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@main
""",
        "spread.yaml": """
backends:
  integration-test: {type: integration-test}
integration-suites:
  k8s/tests/integration/:
    working-dir: k8s
    backends: [integration-test]
    environment:
      CONCIERGE: concierge-k8s.yaml
""",
        "concierge-k8s.yaml": "juju: {channel: 4/stable}\nproviders: {k8s: {}}",
    }
    machine = evaluate_files(EvaluationUnit("machine", ProductType.CHARM, "a/b", "machine"), source)
    kubernetes = evaluate_files(EvaluationUnit("k8s", ProductType.CHARM, "a/b", "k8s"), source)
    assert machine["supports_canonical_k8s"].state == MetricState.NOT_APPLICABLE
    for key in ("uses_ops_testing", "uses_jubilant", "uses_charm_ci", "supports_juju_4"):
        assert machine[key] == measured(False)
        assert kubernetes[key] == measured(True)
    assert kubernetes["supports_canonical_k8s"] == measured(True)


@responses.activate
def test_charmhub_error_fails_the_runner():
    from scorers.test_verification.logic import compute_v0_metrics

    github_snapshot(tip_checks=[check("test")])
    responses.replace(
        responses.GET,
        "https://api.charmhub.io/v2/charms/info/example",
        status=503,
    )
    with pytest.raises(Exception, match="503"):
        compute_v0_metrics(UNIT)


@responses.activate
def test_missing_published_branch_is_insufficient():
    from scorers.test_verification.logic import compute_v0_metrics

    base = github_snapshot(tracks=("latest", "1"), tip_checks=[check("unit")])
    responses.get(base + "/branches/track%2F1", status=404)
    assert compute_v0_metrics(UNIT)["ci_passing"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_ruleset_required_missing_job_is_insufficient():
    from scorers.test_verification.logic import compute_v0_metrics

    base = github_snapshot(tip_checks=[check("unit")])
    responses.replace(
        responses.GET,
        base + "/rules/branches/main",
        json=[
            {
                "type": "required_status_checks",
                "parameters": {"required_status_checks": [{"context": "integration"}]},
            }
        ],
    )
    assert compute_v0_metrics(UNIT)["ci_passing"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_check_pages_do_not_discard_later_failures():
    from scorers.test_verification.logic import compute_v0_metrics

    base = github_snapshot(tip_checks=[check("unit")])
    responses.replace(
        responses.GET,
        base + "/commits/tip/check-runs",
        json={"check_runs": [check(f"unit-{i}") for i in range(100)]},
    )
    responses.get(base + "/commits/tip/check-runs", json={"check_runs": [check("last", "failure")]})
    assert compute_v0_metrics(UNIT)["ci_passing"] == measured(False)


@responses.activate
def test_acquisition_failure_is_not_empty_success():
    from scorers.test_verification.logic import compute_v0_metrics

    responses.get("https://api.github.com/repos/canonical/example", status=503)
    with pytest.raises(Exception, match="503"):
        compute_v0_metrics(UNIT)
