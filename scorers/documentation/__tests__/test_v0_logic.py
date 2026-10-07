import base64

import pytest
import responses
from openai import APIError

from engine.metric_outcomes import MetricState, measured
from engine.models import EvaluationUnit, ProductType
from scorers.documentation import logic
from scorers.shared.github_signals import GitHubAcquisitionError

UNIT = EvaluationUnit("product", ProductType.CHARM, "canonical/product", subpath="component")
TEMPLATE_SHA = "8299de3ec4a264c853d48c6bb09903677e38cbd7"
API = "https://api.github.com/repos"


def file_response(repo, path, text, *, ref=None, status=200):
    url = f"{API}/{repo}/contents/{path}"
    if ref:
        url += f"?ref={ref}"
    responses.get(
        url,
        json={"encoding": "base64", "content": base64.b64encode(text.encode()).decode()},
        status=status,
    )


def evidence(
    *,
    readme="Product documentation.",
    contributing="Run the test suite.",
    security="Contact our security team.",
    version="2.0",
):
    for path, content in (
        ("README.md", readme),
        ("CONTRIBUTING.md", contributing),
        ("SECURITY.md", security),
    ):
        file_response(UNIT.repo, path, content)
        file_response(
            "canonical/platform-engineering-charm-template",
            path,
            f"# {path}\n\nDefault template text.",
            ref=TEMPLATE_SHA,
        )
    file_response(UNIT.repo, "docs/_dev/version", version)


@responses.activate
def test_v0_only_outputs_target_metrics_and_uses_root_files(mocker):
    evidence()
    client = mocker.patch.object(logic, "OpenAI")
    result = logic.compute_v0_metrics(UNIT, "token", "")
    assert set(result) == {
        "readme_present",
        "contributing_present",
        "has_security",
        "uses_sphinx_stack",
        "diataxis_coverage_ai",
    }
    assert result["readme_present"] == measured(True)
    assert result["contributing_present"] == measured(True)
    assert result["has_security"] == measured(True)
    assert result["uses_sphinx_stack"] == measured("2.0")
    assert result["diataxis_coverage_ai"].state == MetricState.INSUFFICIENT_DATA
    client.assert_not_called()


@pytest.mark.parametrize(
    "content",
    [
        "",
        " \r\n",
        "# Title",
        "# Title\n\n## Section",
        "Title\n=====\n\n<!-- Replace this file -->",
        "# README.md\r\n\r\nDefault \t template   text.\r\n",
    ],
)
@responses.activate
def test_root_file_rejects_empty_headings_and_normalized_template(content):
    evidence(readme=content)
    assert logic.compute_v0_metrics(UNIT, "", "")["readme_present"] == measured(False)


@responses.activate
def test_security_uses_exact_same_deterministic_criterion():
    evidence(security="# SECURITY.md\n\nDefault template text.")
    assert logic.compute_v0_metrics(UNIT, "", "")["has_security"] == measured(False)


@pytest.mark.parametrize(
    "path,key",
    [
        ("README.md", "readme_present"),
        ("CONTRIBUTING.md", "contributing_present"),
        ("SECURITY.md", "has_security"),
    ],
)
@pytest.mark.parametrize("customized", [False, True])
@responses.activate
def test_template_comparison_ignores_comments_but_preserves_body_changes(path, key, customized):
    evidence()
    template = f"# {path}\n\nDefault template text."
    template += "\n<!-- Original template comment -->"
    body = "Product-specific guidance." if customized else "Default template text."
    content = f"# {path}\n\n{body}\n<!-- Updated\nproduct comment -->"
    responses.replace(
        responses.GET,
        f"{API}/canonical/platform-engineering-charm-template/contents/{path}?ref={TEMPLATE_SHA}",
        json={"encoding": "base64", "content": base64.b64encode(template.encode()).decode()},
    )
    responses.replace(
        responses.GET,
        f"{API}/{UNIT.repo}/contents/{path}",
        json={"encoding": "base64", "content": base64.b64encode(content.encode()).decode()},
    )
    assert logic.compute_v0_metrics(UNIT, "", "")[key] == measured(customized)


@responses.activate
def test_adapted_template_is_not_rejected_by_placeholder_token_heuristics():
    evidence(readme="# Product\n\n{{ project_name }} uses our customized documentation.")
    assert logic.compute_v0_metrics(UNIT, "", "")["readme_present"] == measured(True)


@pytest.mark.parametrize("version", ["0.1", "1.2.3", "2.0rc1", "v2.0", " 2.0\n"])
@responses.activate
def test_sphinx_accepts_valid_versions_without_minimum(version):
    evidence(version=version)
    assert logic.compute_v0_metrics(UNIT, "", "")["uses_sphinx_stack"] == measured(version.strip())


@pytest.mark.parametrize("version", ["", "latest", "2.0\n3.0", "2.invalid", "deadbeef"])
@responses.activate
def test_sphinx_invalid_versions_are_measured_non_adoption(version):
    evidence(version=version)
    assert logic.compute_v0_metrics(UNIT, "", "")["uses_sphinx_stack"] == measured("")


@responses.activate
def test_missing_sphinx_version_is_measured_non_adoption():
    evidence()
    responses.replace(
        responses.GET,
        f"{API}/{UNIT.repo}/contents/docs/_dev/version",
        status=404,
        json={"message": "Not Found"},
    )
    assert logic.compute_v0_metrics(UNIT, "", "")["uses_sphinx_stack"] == measured("")


@pytest.mark.parametrize("status", [401, 403, 429, 500])
@responses.activate
def test_required_file_acquisition_fails_closed(status):
    evidence()
    responses.replace(
        responses.GET,
        f"{API}/{UNIT.repo}/contents/README.md",
        status=status,
        json={"message": "failure"},
    )
    with pytest.raises(GitHubAcquisitionError):
        logic.compute_v0_metrics(UNIT, "", "")


@responses.activate
def test_missing_pinned_template_is_not_a_success():
    evidence()
    responses.replace(
        responses.GET,
        f"{API}/canonical/platform-engineering-charm-template/contents/README.md?ref={TEMPLATE_SHA}",
        status=404,
        json={"message": "Not Found"},
    )
    with pytest.raises(GitHubAcquisitionError):
        logic.compute_v0_metrics(UNIT, "", "")


@pytest.mark.parametrize(
    "kwargs,product_type",
    [
        ({}, ProductType.SNAP),
        ({"has_user_facing_docs": False}, ProductType.CHARM),
    ],
)
@responses.activate
def test_sphinx_exemptions_are_explicit(kwargs, product_type):
    evidence()
    unit = EvaluationUnit("any-name", product_type, UNIT.repo)
    result = logic.compute_v0_metrics(unit, "", "", **kwargs)
    assert result["uses_sphinx_stack"].state == MetricState.NOT_APPLICABLE
    assert not any("/_dev/version" in call.request.url for call in responses.calls)


@responses.activate
def test_sphinx_uses_reviewed_product_exemption_reason():
    evidence()
    unit = EvaluationUnit(
        "any-name",
        ProductType.CHARM,
        UNIT.repo,
        documentation_exemption="Fork publishes upstream-maintained documentation.",
    )
    outcome = logic.compute_v0_metrics(unit, "", "")["uses_sphinx_stack"]
    assert outcome.state == MetricState.NOT_APPLICABLE
    assert outcome.reason == unit.documentation_exemption
    assert not any("/_dev/version" in call.request.url for call in responses.calls)


@responses.activate
def test_component_docs_scope_is_explicit():
    evidence()
    file_response(UNIT.repo, "component/docs/_dev/version", "3.0")
    result = logic.compute_v0_metrics(UNIT, "", "", docs_path="component/docs")
    assert result["uses_sphinx_stack"] == measured("3.0")


def model_response(mocker, raw):
    client = mocker.Mock()
    client.chat.completions.create.return_value = mocker.Mock(
        choices=[mocker.Mock(message=mocker.Mock(content=raw))]
    )
    mocker.patch.object(logic, "OpenAI", return_value=client)
    return client


def docs_evidence(repo, path, text):
    responses.get(
        f"{API}/{repo}/contents/{path}",
        json=[
            {"type": "file", "path": f"{path}/tutorial.md", "name": "tutorial.md"},
            {"type": "file", "path": f"{path}/reference.rst", "name": "reference.rst"},
        ],
    )
    file_response(repo, f"{path}/tutorial.md", text)
    file_response(repo, f"{path}/reference.rst", "Configure the documented options. " * 10)


@responses.activate
def test_diataxis_reads_authoritative_docs_not_readme_only(mocker):
    evidence()
    file_response(UNIT.repo, "manual/_dev/version", "2.0")
    docs_evidence("canonical/upstream-docs", "manual", "Learn the product step by step. " * 10)
    client = model_response(
        mocker, '{"diataxis_coverage": 2, "reasoning": "Tutorial and reference"}'
    )
    result = logic.compute_v0_metrics(
        UNIT, "", "key", "test/model", docs_repo="canonical/upstream-docs", docs_path="manual"
    )
    assert result["diataxis_coverage_ai"].value == 2
    payload = client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "step by step" in payload
    assert result["diataxis_coverage_ai"].reason == "Tutorial and reference"


@pytest.mark.parametrize(
    "raw",
    [
        "not JSON",
        '{"diataxis_coverage": 10}',
        '{"diataxis_coverage": true}',
        '{"diataxis_coverage": "3"}',
        '{"reasoning": "No score"}',
    ],
)
@responses.activate
def test_invalid_ai_evidence_is_unavailable_not_zero(mocker, raw):
    evidence()
    docs_evidence(UNIT.repo, "docs", "Meaningful documentation content. " * 10)
    model_response(mocker, raw)
    result = logic.compute_v0_metrics(UNIT, "", "key", "test/model")
    assert result["diataxis_coverage_ai"].state == MetricState.INSUFFICIENT_DATA


@responses.activate
def test_absent_docs_are_unavailable_without_model_call(mocker):
    evidence()
    responses.get(f"{API}/{UNIT.repo}/contents/docs", status=404)
    client = mocker.patch.object(logic, "OpenAI")
    assert (
        logic.compute_v0_metrics(UNIT, "", "key")["diataxis_coverage_ai"].state
        == MetricState.INSUFFICIENT_DATA
    )
    client.assert_not_called()


@responses.activate
def test_model_failure_is_unavailable_without_exposing_error(mocker):
    evidence()
    docs_evidence(UNIT.repo, "docs", "Meaningful documentation content. " * 10)
    client = model_response(mocker, "")
    client.chat.completions.create.side_effect = APIError(
        "sensitive provider detail", request=mocker.Mock(), body=None
    )
    outcome = logic.compute_v0_metrics(UNIT, "", "key")["diataxis_coverage_ai"]
    assert outcome.state == MetricState.INSUFFICIENT_DATA
    assert "sensitive" not in outcome.reason


@responses.activate
def test_measured_zero_is_distinct_from_unavailable(mocker):
    evidence()
    docs_evidence(UNIT.repo, "docs", "Unstructured support information. " * 10)
    model_response(mocker, '{"diataxis_coverage": 0, "reasoning": "No meaningful modes"}')
    outcome = logic.compute_v0_metrics(UNIT, "", "key")["diataxis_coverage_ai"]
    assert outcome.state == MetricState.MEASURED
    assert outcome.value == 0


@responses.activate
def test_short_docs_are_insufficient_without_model_call(mocker):
    evidence()
    responses.get(
        f"{API}/{UNIT.repo}/contents/docs",
        json=[
            {"type": "file", "path": "docs/index.md", "name": "index.md"},
        ],
    )
    file_response(UNIT.repo, "docs/index.md", "# Product\n\nBrief description.")
    client = mocker.patch.object(logic, "OpenAI")
    assert (
        logic.compute_v0_metrics(UNIT, "", "key")["diataxis_coverage_ai"].state
        == MetricState.INSUFFICIENT_DATA
    )
    client.assert_not_called()


@responses.activate
def test_docs_acquisition_failures_do_not_become_zero(mocker):
    evidence()
    responses.get(f"{API}/{UNIT.repo}/contents/docs", status=503)
    with pytest.raises(GitHubAcquisitionError):
        logic.compute_v0_metrics(UNIT, "", "key")


@responses.activate
def test_missing_root_file_is_measured_false():
    evidence()
    responses.replace(responses.GET, f"{API}/{UNIT.repo}/contents/README.md", status=404)
    assert logic.compute_v0_metrics(UNIT, "", "")["readme_present"] == measured(False)


@responses.activate
def test_no_user_docs_makes_informational_coverage_not_applicable(mocker):
    evidence()
    client = mocker.patch.object(logic, "OpenAI")
    result = logic.compute_v0_metrics(UNIT, "", "key", has_user_facing_docs=False)
    assert result["diataxis_coverage_ai"].state == MetricState.NOT_APPLICABLE
    client.assert_not_called()
