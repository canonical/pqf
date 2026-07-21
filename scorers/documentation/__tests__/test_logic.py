from unittest.mock import MagicMock

import responses

from engine.models import EvaluationUnit, ProductType
from scorers.documentation.logic import (
    _check_file_exists,
    _check_url_alive,
    compute_metrics,
)

UNIT = EvaluationUnit(
    product_id="matrix",
    product_type=ProductType.CHARM,
    repo="canonical/synapse-operator",
    documentation_url="https://charmhub.io/synapse",
)

UNIT_NO_REPO = EvaluationUnit(
    product_id="matrix",
    product_type=ProductType.CHARM,
    repo="",
    documentation_url="",
)

_README = "# Synapse\n\n## Getting started\n\nThis tutorial shows you how to deploy...\n"


@responses.activate
def test_check_file_exists_true():
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/synapse-operator/contents/README.md",
        json={"name": "README.md"},
        status=200,
    )
    assert _check_file_exists("canonical/synapse-operator", "README.md", "token") is True


@responses.activate
def test_check_file_exists_false_on_404():
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/synapse-operator/contents/CONTRIBUTING.md",
        status=404,
    )
    assert _check_file_exists("canonical/synapse-operator", "CONTRIBUTING.md", "token") is False


@responses.activate
def test_check_file_exists_retries_without_auth_on_public_repo_404():
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/synapse-operator/contents/README.md",
        status=404,
        match=[responses.matchers.header_matcher({"Authorization": "Bearer gh-token"})],
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/canonical/synapse-operator/contents/README.md",
        json={"name": "README.md"},
        status=200,
        match=[responses.matchers.header_matcher({})],
    )

    assert _check_file_exists("canonical/synapse-operator", "README.md", "gh-token") is True


@responses.activate
def test_check_url_alive_true():
    responses.add(responses.GET, "https://charmhub.io/synapse", status=200)
    assert _check_url_alive("https://charmhub.io/synapse") is True


@responses.activate
def test_check_url_alive_false_on_404():
    responses.add(responses.GET, "https://charmhub.io/synapse", status=404)
    assert _check_url_alive("https://charmhub.io/synapse") is False


def test_compute_metrics_happy_path(mocker):
    mocker.patch(
        "scorers.documentation.logic._check_file_exists",
        side_effect=lambda repo, fname, token: (
            fname in {"README.md", "CONTRIBUTING.md", "SECURITY.md"}
        ),
    )
    mocker.patch("scorers.documentation.logic._check_url_alive", return_value=True)
    mocker.patch(
        "scorers.documentation.logic._fetch_readme",
        return_value=_README,
    )
    mock_client = MagicMock()
    mocker.patch("scorers.documentation.logic._make_openrouter_client", return_value=mock_client)
    mock_client.chat.completions.create.side_effect = [
        MagicMock(
            choices=[
                MagicMock(message=MagicMock(content='{"diataxis_coverage": 2, "reasoning": "ok"}'))
            ]
        ),
        MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content='{"style_linter_passing": false, "reasoning": "ok"}')
                )
            ]
        ),
    ]

    result = compute_metrics(UNIT, "gh-token", "or-key", model="openrouter/test-model")
    assert result["has_readme"] is True
    assert result["has_contributing"] is True
    assert result["has_security"] is True
    assert result["links_passing"] is True
    assert result["diataxis_coverage"] == 2
    assert result["style_linter_passing"] is False
    assert mock_client.chat.completions.create.call_count == 2
    assert all(
        call.kwargs["model"] == "openrouter/test-model"
        for call in mock_client.chat.completions.create.call_args_list
    )


def test_compute_metrics_skips_llm_when_no_api_key(mocker):
    """When OPENROUTER_API_KEY is empty, LLM metrics default to 0/False."""
    mocker.patch(
        "scorers.documentation.logic._check_file_exists",
        side_effect=lambda repo, fname, token: fname == "README.md",
    )
    mocker.patch("scorers.documentation.logic._check_url_alive", return_value=False)
    mock_llm = mocker.patch("scorers.documentation.logic._make_openrouter_client")

    result = compute_metrics(UNIT, "gh-token", "")
    assert result["has_readme"] is True
    assert result["diataxis_coverage"] == 0
    assert result["style_linter_passing"] is False
    mock_llm.assert_not_called()
