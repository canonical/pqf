import base64

import pytest
import responses

from engine.metric_outcomes import MetricState, measured
from engine.models import EvaluationUnit, ProductType
from scorers.test_verification.v0 import evaluate_files

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


@pytest.mark.parametrize(
    ("track", "value"),
    [
        ("4/stable", True),
        ("4.0/stable", True),
        ("4.1/stable", True),
        ("4/edge", False),
        ("4.1/beta", False),
        ("40/stable", False),
        ("3/stable", False),
        ("4/stable/foo", False),
    ],
)
def test_major_juju_track_accepts_any_stable_release_in_the_line(track, value):
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
    assert result["supports_juju_4"] == measured(value)


@pytest.mark.parametrize(("track", "value"), [("3.6/stable", True), ("3/stable", False)])
def test_pinned_lts_track_requires_exact_release(track, value):
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
    assert result["supports_juju_lts"] == measured(value)


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


def test_matrix_object_properties_resolve_unit_job_scope():
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/test.yml": """
jobs:
  test:
    strategy:
      matrix:
        charm:
          - {name: example, working-directory: ./charm}
          - {name: other, working-directory: ./other}
    uses: canonical/operator-workflows/.github/workflows/test.yaml@main
    with:
      working-directory: ${{ matrix.charm.working-directory }}
"""
            }
        ),
    )
    assert result["uses_gh_runners_unit_testing"] == measured(True)


def test_unresolvable_non_test_steps_job_does_not_hide_unit_runner_evidence():
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/test.yml": """
jobs:
  unit:
    uses: canonical/operator-workflows/.github/workflows/test.yaml@main
    with:
      working-directory: ./charm
""",
                ".github/workflows/publish.yml": """
jobs:
  publish:
    strategy:
      matrix:
        charm-dir: ${{ fromJSON(needs.find.outputs.dirs) }}
    runs-on: ubuntu-latest
    steps:
      - run: charmcraft upload ${{ matrix.charm-dir }}
""",
            }
        ),
    )
    assert result["uses_gh_runners_unit_testing"] == measured(True)


def test_unresolvable_test_steps_job_remains_insufficient():
    result = evaluate_files(
        UNIT,
        files(
            {
                ".github/workflows/test.yml": """
jobs:
  unit:
    strategy:
      matrix:
        dir: ${{ fromJSON(needs.find.outputs.dirs) }}
    runs-on: ${{ matrix.runner }}
    steps:
      - run: tox -e unit
        working-directory: ${{ matrix.dir }}
""",
            }
        ),
    )
    assert result["uses_gh_runners_unit_testing"].state == MetricState.INSUFFICIENT_DATA


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


def test_charm_without_metadata_at_scope_is_insufficient_not_noncompliant():
    result = evaluate_files(
        EvaluationUnit("example", ProductType.CHARM, "canonical/example"),
        files({"charm/tests/unit/test_charm.py": "from ops import testing\n"}),
    )
    assert result
    assert all(
        outcome.state == MetricState.INSUFFICIENT_DATA
        and "No charm metadata" in (outcome.reason or "")
        for outcome in result.values()
    )


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


def github_snapshot(*, charm=True):
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
    return base


@pytest.mark.parametrize("charm", [True, False])
@responses.activate
def test_runner_returns_contract_outputs_without_ci_or_charmhub_calls(charm):
    from scorers.test_verification.logic import compute_v0_metrics

    github_snapshot(charm=charm)
    product_type = ProductType.CHARM if charm else ProductType.SNAP
    result = compute_v0_metrics(EvaluationUnit("example", product_type, "canonical/example"))
    assert set(result) == {
        "uses_ops_testing",
        "uses_gh_runners_unit_testing",
        "uses_jubilant",
        "uses_tf_v1_provider",
        "uses_charm_ci",
        "supports_canonical_k8s",
        "supports_juju_4",
        "supports_juju_lts",
    }
    if not charm:
        assert all(value.state == MetricState.NOT_APPLICABLE for value in result.values())
    assert not any(
        "charmhub" in call.request.url or "/commits/" in call.request.url
        for call in responses.calls
    )


@responses.activate
def test_arbitrary_linked_config_is_acquired_and_api_failure_propagates():
    from scorers.test_verification.logic import compute_v0_metrics

    base = github_snapshot()
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


def test_traefik_issue_42_linked_concierge_and_configured_tracks():
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
    assert result["supports_juju_4"] == measured(True)


GOPKG_SPREAD = """
backends:
  integration-test:
    type: integration-test
    systems: [ubuntu-24.04]
  integration-test-juju4:
    type: integration-test
    systems: [ubuntu-24.04]
    environment:
      CONCIERGE: concierge-juju4.yaml
  docs:
    type: opcli-minimal
environment:
  CONCIERGE: concierge-lxd.yaml
integration-suites:
  app/charm/tests/integration/:
    working-dir: app/charm/
    backends: [integration-test, integration-test-juju4]
"""


def gopkg_files(include):
    with_include = f'\n      spread-jobs-include: "{include}"' if include else ""
    return {
        "app/charm/charmcraft.yaml": "name: gopkg-k8s\ncontainers: {app: {}}",
        ".github/workflows/integration-test.yaml": f"""
jobs:
  integration-test:
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@v1.0.1
    with:
      working-directory: .{with_include}
""",
        "spread.yaml": GOPKG_SPREAD,
        "concierge-lxd.yaml": "juju: {channel: 3.6/stable}\nproviders: {k8s: {}}",
        "concierge-juju4.yaml": "juju: {channel: 4/stable}\nproviders: {k8s: {}}",
    }


GOPKG = EvaluationUnit("gopkg-k8s", ProductType.CHARM, "canonical/gopkg-charmed", "app/charm")


@pytest.mark.parametrize("include", ["", "integration-test*-ci:*", "*:*"])
def test_backend_environment_selects_concierge_per_backend(include):
    result = evaluate_files(GOPKG, gopkg_files(include))
    assert result["uses_charm_ci"] == measured(True)
    assert result["supports_juju_4"] == measured(True)
    assert result["supports_juju_lts"] == measured(True)
    assert result["supports_canonical_k8s"] == measured(True)


def test_literal_include_filter_excludes_unselected_backends():
    result = evaluate_files(GOPKG, gopkg_files("integration-test-ci:*"))
    assert result["supports_juju_lts"] == measured(True)
    assert result["supports_juju_4"] == measured(False)


@pytest.mark.parametrize(
    "include", ["*tests/integration*", "*-ci:ubuntu-24.04:*", "*:build/app/charm/*"]
)
def test_include_filter_is_matched_against_generated_selectors(include):
    result = evaluate_files(GOPKG, gopkg_files(include))
    assert result["supports_juju_4"] == measured(True)
    assert result["supports_juju_lts"] == measured(True)


def test_include_filter_matching_no_selector_excludes_suite():
    result = evaluate_files(GOPKG, gopkg_files("*:ubuntu-22.04:*"))
    assert result["supports_juju_4"] == measured(False)


def test_aproxy_explicit_module_variants_with_default_concierge_expression():
    result = evaluate_files(
        EvaluationUnit("aproxy", ProductType.CHARM, "canonical/aproxy-operator"),
        {
            "charmcraft.yaml": "name: aproxy\n",
            ".github/workflows/integration_test.yaml": """
jobs:
  integration-test:
    uses: canonical/charm-ci/.github/workflows/integration-test.yml@v1.0.1
    with:
      working-directory: .
      spread-jobs-include: "*tests/integration*"
""",
            "spread.yaml": """
backends:
  integration-test:
    type: integration-test
    systems:
      - ubuntu-24.04: {runner: [ubuntu-24.04]}
environment:
  CONCIERGE: '$(HOST: echo "${CONCIERGE:-concierge.yaml}")'
integration-suites:
  tests/integration/:
    working-dir: ./
    auto-discover: false
    backends: [integration-test]
    environment:
      MODULE/focal: tests/integration/test_charm.py
""",
            "concierge.yaml": "juju: {channel: 3.6/stable}\nproviders: {lxd: {}}",
        },
    )
    assert result["supports_juju_lts"] == measured(True)
    assert result["supports_juju_4"] == measured(False)


def test_include_filter_selecting_some_variants_is_insufficient():
    source = gopkg_files("*:*:*:legacy")
    source["spread.yaml"] = GOPKG_SPREAD.replace(
        "backends: [integration-test, integration-test-juju4]",
        "backends: [integration-test, integration-test-juju4]\n"
        "    auto-discover: false\n"
        "    environment:\n"
        "      MODULE/legacy: tests/integration/test_legacy.py\n"
        "      MODULE/current: tests/integration/test_current.py",
    )
    result = evaluate_files(GOPKG, source)
    assert result["supports_juju_4"].state == MetricState.INSUFFICIENT_DATA


def test_backend_linked_concierge_paths_are_acquired():
    from scorers.test_verification.evidence import _linked_paths

    source = gopkg_files("")
    source["spread.yaml"] = GOPKG_SPREAD.replace("concierge-juju4.yaml", "env/four.yaml")
    assert "env/four.yaml" in _linked_paths(source)


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
def test_acquisition_failure_is_not_empty_success():
    from scorers.test_verification.logic import compute_v0_metrics

    responses.get("https://api.github.com/repos/canonical/example", status=503)
    with pytest.raises(Exception, match="503"):
        compute_v0_metrics(UNIT)
