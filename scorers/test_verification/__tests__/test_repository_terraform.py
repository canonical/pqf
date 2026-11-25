import base64
import json
from dataclasses import replace
from pathlib import Path

import pytest
import responses

from engine.framework import discover_frameworks, get_framework
from engine.metric_outcomes import MetricState, measured
from engine.models import EvaluationUnit, ProductType
from scorers import registry
from scorers.shared.github_signals import GitHubAcquisitionError
from scorers.test_verification.evidence import acquire
from scorers.test_verification.logic import compute_v0_metrics
from scorers.test_verification.terraform import terraform_outcome
from scorers.test_verification.v0 import evaluate_files

UNIT = EvaluationUnit("example", ProductType.CHARM, "canonical/example", subpath="charm")
VALID = """
terraform {
  required_providers {
    juju = { source = "juju/juju", version = ">= 2.2.0" }
  }
}
"""
INVALID = VALID.replace(">= 2.2.0", "~> 0.20")
NON_JUJU = """
terraform {
  required_providers {
    kubernetes = { source = "hashicorp/kubernetes" }
  }
}
resource "kubernetes_namespace" "test" { metadata { name = "test" } }
"""


@pytest.mark.parametrize(
    "path",
    [
        "terraform/versions.tf",
        "terraform/product/versions.tf",
        "terraform/product/tests/setup/main.tf",
        "other-charm/terraform/versions.tf",
        "docs/terraform/versions.tf",
    ],
)
def test_repository_measurement_includes_every_location(path):
    outcome = terraform_outcome({"charm/terraform/versions.tf": VALID, path: INVALID})
    assert outcome.state == MetricState.MEASURED
    assert outcome.value is False
    assert path in outcome.reason


def test_explicit_non_juju_utility_does_not_fail_juju_compliance():
    assert terraform_outcome(
        {"terraform/versions.tf": VALID, "tests/namespace/main.tf": NON_JUJU}
    ) == measured(True)
    assert (
        terraform_outcome({"tests/namespace/main.tf": NON_JUJU}).state == MetricState.NOT_APPLICABLE
    )


@pytest.mark.parametrize(
    "extra",
    [
        'module "charm" { source = "../charm" }',
        'resource "juju_application" "app" { name = "app" }',
        'provider "juju" {}',
        'data "juju_model" "model" { name = "test" }',
    ],
)
def test_non_juju_provider_does_not_hide_missing_juju_requirements(extra):
    outcome = terraform_outcome({"terraform/main.tf": NON_JUJU + extra})
    assert outcome.value is False
    assert "no explicit juju/juju" in outcome.reason


def test_unclassified_module_without_provider_requirement_fails():
    outcome = terraform_outcome({"terraform/main.tf": 'locals { name = "test" }'})
    assert outcome.value is False
    assert "terraform" in outcome.reason


def test_malformed_utility_is_unknown_not_excluded():
    outcome = terraform_outcome(
        {"terraform/versions.tf": VALID, "tests/namespace/main.tf": "terraform {"}
    )
    assert outcome.state == MetricState.INSUFFICIENT_DATA
    assert "tests/namespace/main.tf" in outcome.reason


def test_no_terraform_is_not_applicable():
    assert terraform_outcome({}).state == MetricState.NOT_APPLICABLE


def test_terraform_json_and_unrelated_utility_are_included():
    files = {
        "tests/namespace/main.tf": NON_JUJU,
        "terraform/product/versions.tf.json": json.dumps(
            {
                "terraform": {
                    "required_providers": {
                        "controller": {
                            "source": "registry.terraform.io/juju/juju",
                            "version": ">= 2.2.0, < 3.0",
                        }
                    }
                }
            }
        ),
    }
    assert terraform_outcome(files) == measured(True)


def test_unreadable_provider_identity_cannot_be_excluded():
    outcome = terraform_outcome(
        {
            "utility/versions.tf": "terraform { required_providers { "
            "kubernetes = { source = var.provider_source } } }"
        }
    )
    assert outcome.state == MetricState.INSUFFICIENT_DATA


def test_unknown_resource_provider_is_not_classified_as_non_juju():
    outcome = terraform_outcome(
        {"utility/main.tf": NON_JUJU + 'resource "custom_application" "app" {}'}
    )
    assert outcome.value is False


@pytest.mark.parametrize("source", ["/", "hashicorp//kubernetes", "invalid source/kubernetes"])
def test_malformed_non_juju_sources_do_not_hide_unclassified_modules(source):
    outcome = terraform_outcome(
        {"utility/main.tf": NON_JUJU.replace("hashicorp/kubernetes", source)}
    )
    assert outcome.value is False


def snapshot(contents):
    base = "https://api.github.com/repos/canonical/example"
    responses.get(base, json={"default_branch": "main"})
    responses.get(base + "/branches/main", json={"commit": {"sha": "tip"}})
    responses.get(
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
            json={"encoding": "base64", "content": base64.b64encode(text.encode()).decode()},
        )
    return base


def test_existing_v0_evaluator_measures_repository_terraform_without_charm_metadata():
    result = evaluate_files(UNIT, {"terraform/product/versions.tf": INVALID})
    assert result["uses_tf_v1_provider"].value is False
    assert "terraform/product/versions.tf" in result["uses_tf_v1_provider"].reason
    assert result["uses_ops_testing"].state == MetricState.INSUFFICIENT_DATA


def test_existing_v0_evaluator_includes_sibling_charm_terraform():
    result = evaluate_files(
        UNIT,
        {
            "charm/charmcraft.yaml": "name: example",
            "charm/terraform/versions.tf": VALID,
            "other/charmcraft.yaml": "name: other",
            "other/terraform/versions.tf": INVALID,
        },
    )
    assert result["uses_tf_v1_provider"].value is False
    assert "other/terraform/versions.tf" in result["uses_tf_v1_provider"].reason


@responses.activate
def test_v0_dispatch_acquires_bundles_without_broadening_other_metrics():
    snapshot(
        {
            "charm/charmcraft.yaml": "name: example",
            "charm/tests/unit/test_app.py": "from ops.testing import Context",
            "other/tests/unit/test_app.py": "from ops.testing import Harness",
            "terraform/versions.tf": VALID,
            "terraform/product/tests/setup/main.tf": INVALID,
        }
    )
    framework = get_framework(discover_frameworks(Path("framework/versions")), "v0")
    result = registry.run_dimension(
        UNIT,
        "test_verification",
        framework.dimensions["dimensions"]["test_verification"],
        registry.ScorerContext("token"),
    )
    assert result["uses_ops_testing"] == measured(True)
    assert result["uses_tf_v1_provider"].value is False
    assert "terraform/product/tests/setup/main.tf" in result["uses_tf_v1_provider"].reason


@responses.activate
def test_repository_evidence_is_shared_without_charm_metadata():
    snapshot({"terraform/product/versions.tf": INVALID})
    first = compute_v0_metrics(UNIT)
    second = compute_v0_metrics(replace(UNIT, product_id="other", subpath="other"))
    assert first == second
    assert first["uses_tf_v1_provider"].value is False


@responses.activate
def test_acquisition_is_repository_wide_for_terraform_only():
    snapshot(
        {
            "charm/charmcraft.yaml": "name: example",
            "terraform/versions.tf": INVALID,
            "charm/tests/unit/test_app.py": "from ops.testing import Context",
            "other/tests/unit/test_app.py": "from ops.testing import Harness",
        }
    )
    evidence = acquire(UNIT, None)
    assert "terraform/versions.tf" in evidence
    assert "charm/tests/unit/test_app.py" in evidence
    assert "other/tests/unit/test_app.py" not in evidence


@responses.activate
def test_repository_terraform_blob_failure_propagates():
    base = snapshot({"terraform/versions.tf": VALID})
    responses.replace(responses.GET, base + "/git/blobs/blob-0", status=403)
    with pytest.raises(GitHubAcquisitionError, match="403"):
        compute_v0_metrics(UNIT)


@responses.activate
def test_truncated_repository_tree_does_not_become_no_modules():
    base = snapshot({})
    responses.replace(responses.GET, base + "/git/trees/tip", json={"tree": [], "truncated": True})
    with pytest.raises(ValueError, match="truncated"):
        compute_v0_metrics(UNIT)


@responses.activate
def test_snaps_do_not_acquire_terraform():
    result = compute_v0_metrics(replace(UNIT, product_type=ProductType.SNAP))
    assert result["uses_tf_v1_provider"].state == MetricState.NOT_APPLICABLE
