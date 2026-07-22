from engine.models import EvaluationUnit, ProductType
from scorers.documentation.logic import compute_metrics

UNIT = EvaluationUnit(
    product_id="matrix",
    product_type=ProductType.CHARM,
    repo="canonical/synapse-operator",
    documentation_url="https://canonical.synapse.readthedocs-hosted.com/",
)


def test_compute_metrics_detects_documentation_signals(mocker):
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: path
        in {
            "README.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            ".github/release-drafter.yml",
            "docs/release-notes.md",
            "docs/tutorial.md",
            "docs/how-to.md",
            "docs/reference.md",
            "docs/explanation.md",
        },
    )
    mocker.patch(
        "scorers.documentation.logic.repo_file_text",
        side_effect=lambda repo, path, token: {
            "README.md": (
                "# Synapse\n\n## Overview\n\n## Getting started\n\n## Support\n"
            ),
            "CONTRIBUTING.md": (
                "# Contributing\n\n## Development\n\n## Testing\n\n## Governance\n"
            ),
        }.get(path, ""),
    )
    mocker.patch(
        "scorers.documentation.logic.default_branch_check_runs",
        return_value=[
            {"name": "docs lint", "conclusion": "success"},
            {"name": "vale", "conclusion": "success"},
            {"name": "link check", "conclusion": "success"},
            {"name": "docs build", "conclusion": "success"},
            {"name": "playwright tutorial", "conclusion": "success"},
        ],
    )

    result = compute_metrics(UNIT, "gh-token", "or-key", model="openrouter/test-model")

    assert result == {
        "readme_meets_structure": True,
        "contributing_meets_structure": True,
        "has_security": True,
        "documentation_workflows_passing": True,
        "diataxis_coverage": 4,
        "tutorial_tested": True,
        "uses_rtd_hosting": True,
        "recent_release_notes_present": True,
    }


def test_compute_metrics_defaults_signals_when_repo_signals_missing(mocker):
    unit = EvaluationUnit(
        product_id="matrix",
        product_type=ProductType.CHARM,
        repo="canonical/synapse-operator",
        documentation_url="",
    )
    mocker.patch("scorers.documentation.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="")
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])

    result = compute_metrics(unit, "gh-token", "")

    assert result == {
        "readme_meets_structure": False,
        "contributing_meets_structure": False,
        "has_security": False,
        "documentation_workflows_passing": False,
        "diataxis_coverage": 0,
        "tutorial_tested": False,
        "uses_rtd_hosting": False,
        "recent_release_notes_present": False,
    }
