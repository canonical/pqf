import json

import pytest

from engine.metric_outcomes import MetricState
from scorers.test_verification.terraform import terraform_outcome


def requirement(constraint, source="juju/juju"):
    return f"""
terraform {{
  required_providers {{
    juju = {{
      source = "{source}"
      version = "{constraint}"
    }}
  }}
}}
"""


@pytest.mark.parametrize(
    "constraint",
    [">= 1.0, < 3.0", ">= 1.2.3, < 1.3.0", ">= 2.0, < 4.0", " < 3.0 , >= 1.0 "],
)
def test_requires_explicit_provider_range(constraint):
    outcome = terraform_outcome({"terraform/versions.tf": requirement(constraint)})
    assert outcome.state == MetricState.MEASURED
    assert outcome.value is True


@pytest.mark.parametrize(
    "constraint",
    [
        "~> 1.2",
        "~> 1.2.3",
        "= 1.2.3",
        "1.2.3",
        ">= 1.0",
        ">= 2.0",
        "> 1.0, < 3.0",
        ">= 1.0, <= 3.0",
        ">= 1.0, < 3.0, != 2.0",
        ">= 1.0, >= 2.0, < 3.0",
        ">= 1.0, < 3.0, < 4.0",
        "= 1, != 1",
    ],
)
def test_noncanonical_constraints_explain_required_interval(constraint):
    outcome = terraform_outcome({"terraform/versions.tf": requirement(constraint)})
    assert outcome.state == MetricState.MEASURED
    assert outcome.value is False
    assert "terraform/versions.tf" in outcome.reason
    assert constraint in outcome.reason
    assert ">= A, < B" in outcome.reason


def test_traefik_module_and_test_setup_allow_provider_two():
    # Traefik 466ab5f0816af1202bee9883abcf9d13f6395f50 uses this range in both modules.
    outcome = terraform_outcome(
        {
            "terraform/versions.tf": requirement(">= 1.0, < 3.0"),
            "terraform/tests/setup/main.tf": requirement(">= 1.0, < 3.0"),
        }
    )
    assert outcome.value is True


@pytest.mark.parametrize("constraint", ["~> 0.20", ">= 0.12, < 3.0", "< 3.0", "0.17"])
def test_pre_one_requirements_explain_the_module_and_constraint(constraint):
    outcome = terraform_outcome({"terraform/versions.tf": requirement(constraint)})
    assert outcome.state == MetricState.MEASURED
    assert outcome.value is False
    assert "terraform/versions.tf" in outcome.reason
    assert constraint in outcome.reason
    assert "1.0" in outcome.reason


@pytest.mark.parametrize("constraint", [">= 2, < 1", ">= 1, < 1", ">= 1.2.0, < 1.2", "var.version"])
def test_uninterpretable_or_empty_ranges_are_unknown(constraint):
    outcome = terraform_outcome({"versions.tf": requirement(constraint)})
    assert outcome.state == MetricState.INSUFFICIENT_DATA
    assert "versions.tf" in outcome.reason


def test_all_modules_must_meet_the_minimum():
    outcome = terraform_outcome(
        {
            "terraform/versions.tf": requirement(">= 1.0, < 3.0"),
            "terraform/tests/setup/main.tf": requirement(">= 0.20, < 1.0"),
        }
    )
    assert outcome.value is False
    assert "terraform/tests/setup/main.tf" in outcome.reason


def test_hcl_parser_handles_expressions_outside_provider_requirements():
    outcome = terraform_outcome(
        {
            "terraform/main.tf": """
locals {
  model = "test-${formatdate("YYYYMMDDhhmmss", timestamp())}"
}
""",
            "terraform/versions.tf": requirement(">= 1.0, < 3.0"),
        }
    )
    assert outcome.value is True


@pytest.mark.parametrize("constraint, expected", [(">= 1.0, < 3.0", True), ("~> 1.2", False)])
def test_json_provider_alias_and_registry_address(constraint, expected):
    outcome = terraform_outcome(
        {
            "versions.tf.json": json.dumps(
                {
                    "terraform": {
                        "required_providers": {
                            "controller": {
                                "source": "registry.terraform.io/juju/juju",
                                "version": constraint,
                            }
                        }
                    }
                }
            )
        }
    )
    assert outcome.state == MetricState.MEASURED
    assert outcome.value is expected


def test_missing_juju_requirement_explains_module():
    outcome = terraform_outcome({"terraform/main.tf": 'module "app" { source = "../app" }'})
    assert outcome.value is False
    assert "terraform" in outcome.reason
    assert "juju/juju" in outcome.reason


def test_wrong_juju_source_explains_declaration():
    outcome = terraform_outcome({"versions.tf": requirement(">= 1", "other/juju")})
    assert outcome.value is False
    assert "other/juju" in outcome.reason


def test_invalid_hcl_is_unknown_not_noncompliant():
    outcome = terraform_outcome({"versions.tf": "terraform {"})
    assert outcome.state == MetricState.INSUFFICIENT_DATA
    assert "versions.tf" in outcome.reason


def test_no_terraform_is_not_applicable():
    assert terraform_outcome({}).state == MetricState.NOT_APPLICABLE


@pytest.mark.parametrize("source", ['["juju/juju"]', "var.provider_source"])
def test_nonliteral_provider_sources_are_unknown(source):
    outcome = terraform_outcome(
        {
            "versions.tf": "terraform { required_providers { juju = { "
            f'source = {source} version = ">= 1.0"'
            " } } }"
        }
    )
    assert outcome.state == MetricState.INSUFFICIENT_DATA
    assert "versions.tf" in outcome.reason
