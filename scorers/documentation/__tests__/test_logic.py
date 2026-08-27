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
        side_effect=lambda repo, path, token: (
            path
            in {
                "README.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "docs/release-notes/common.yaml",
                "docs/release-notes/releases",
                "docs/release-notes/template",
                "docs/tutorial.md",
                "docs/how-to.md",
                "docs/reference.md",
                "docs/explanation.md",
            }
        ),
    )
    # Mock GitHub releases: two non-draft releases with bodies
    mocker.patch(
        "scorers.documentation.logic.repo_releases",
        return_value=[
            {"tag_name": "v1.1.0", "draft": False, "body": "Release notes for v1.1.0"},
            {"tag_name": "v1.0.0", "draft": False, "body": "Initial release notes"},
        ],
    )
    mocker.patch(
        "scorers.documentation.logic.repo_file_text",
        side_effect=lambda repo, path, token: {
            "README.md": ("# Synapse\n\n## Overview\n\n## Getting started\n\n## Support\n"),
            "CONTRIBUTING.md": (
                "# Contributing\n\n## Development\n\n## Testing\n\n## Governance\n"
            ),
        }.get(path, ""),
    )
    mocker.patch(
        "scorers.documentation.logic.workflow_files",
        return_value=[
            (
                "release-notes.yaml",
                "uses: canonical/release-notes-automation/.github/workflows/action.yml@main",
            )
        ],
    )
    mocker.patch(
        "scorers.documentation.logic.default_branch_check_runs",
        return_value=[
            {"name": "docs lint", "conclusion": "success"},
            {"name": "vale", "conclusion": "success"},
            {"name": "link check", "conclusion": "success"},
            {"name": "docs build", "conclusion": "success"},
        ],
    )
    result = compute_metrics(UNIT, "gh-token", "or-key", model="openrouter/test-model")
    assert result["release_notes_process_implemented"] is True
    assert result["documentation_workflows_passing"] is True


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
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])

    result = compute_metrics(unit, "gh-token", "")

    assert result == {
        "readme_present": False,
        "contributing_present": False,
        "has_security": False,
        "documentation_workflows_passing": False,
        "diataxis_coverage_ai": 0,
        "uses_rtd_hosting": False,
        "release_notes_process_implemented": False,
        "has_changelog": False,
    }
    # Ensure removed keys are not in result
    assert "tutorial_tested" not in result
    assert "recent_release_notes_present" not in result
    assert "diataxis_coverage" not in result


def test_documentation_workflows_use_latest_conclusion(mocker):
    """Ensure workflow pass/fail is determined by the latest conclusion per check-family.

    We simulate multiple check-runs with the same name where a later run fails and expect
    the overall documentation_workflows_passing to be False.
    """
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: (
            path
            in {
                "README.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "docs/tutorial.md",
                "docs/how-to.md",
                "docs/reference.md",
                "docs/explanation.md",
            }
        ),
    )
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="# Docs")
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])
    mocker.patch(
        "scorers.documentation.logic.default_branch_check_runs",
        return_value=[
            {"name": "docs lint", "conclusion": "success", "completed_at": "2026-01-01T00:00:00Z"},
            {"name": "docs lint", "conclusion": "failure", "completed_at": "2026-01-02T00:00:00Z"},
            {"name": "vale", "conclusion": "success", "completed_at": "2026-01-01T00:00:00Z"},
            {"name": "vale", "conclusion": "success", "completed_at": "2026-01-02T00:00:00Z"},
            {"name": "link check", "conclusion": "success", "completed_at": "2026-01-01T00:00:00Z"},
            {"name": "link check", "conclusion": "success", "completed_at": "2026-01-02T00:00:00Z"},
            {"name": "docs build", "conclusion": "success", "completed_at": "2026-01-01T00:00:00Z"},
            {"name": "docs build", "conclusion": "failure", "completed_at": "2026-01-02T00:00:00Z"},
        ],
    )

    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["documentation_workflows_passing"] is False


def test_documentation_workflows_do_not_require_style_check(mocker):
    """Lint + links + docs build should be sufficient for this contract."""
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: (
            path in {"README.md", "CONTRIBUTING.md", "SECURITY.md"}
        ),
    )
    mocker.patch(
        "scorers.documentation.logic.repo_file_text",
        side_effect=lambda repo, path, token: {
            "README.md": "# Docs\n\n## Overview\n\n## Getting started\n\n## Support\n",
            "CONTRIBUTING.md": "# Contributing\n\n## Development\n\n## Testing\n\n## Governance\n",
        }.get(path, ""),
    )
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])
    mocker.patch(
        "scorers.documentation.logic.default_branch_check_runs",
        return_value=[
            {"name": "docs lint", "conclusion": "success"},
            {"name": "link check", "conclusion": "success"},
            {"name": "docs build", "conclusion": "success"},
        ],
    )

    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["documentation_workflows_passing"] is True


def test_docs_workflow_family_names_are_accepted(mocker):
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: (
            path in {"README.md", "CONTRIBUTING.md", "SECURITY.md"}
        ),
    )
    mocker.patch(
        "scorers.documentation.logic.repo_file_text",
        side_effect=lambda repo, path, token: {
            "README.md": "# Docs\n\n## Overview\n\n## Getting started\n\n## Support\n",
            "CONTRIBUTING.md": "# Contributing\n\n## Development\n\n## Testing\n\n## Governance\n",
        }.get(path, ""),
    )
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])
    mocker.patch(
        "scorers.documentation.logic.default_branch_check_runs",
        return_value=[
            {"name": "docs-checks / vale", "conclusion": "success"},
            {"name": "docs-checks / linkcheck", "conclusion": "success"},
            {"name": "docs-checks / docs build", "conclusion": "success"},
        ],
    )

    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["documentation_workflows_passing"] is True


def test_release_notes_requires_canonical_workflow_and_structure(mocker):
    """Release notes process requires canonical workflow reference + structure evidence."""
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: (
            path
            in {
                "docs/release-notes/common.yaml",
                "docs/release-notes/releases",
                "docs/release-notes/template",
            }
        ),
    )
    mocker.patch(
        "scorers.documentation.logic.workflow_files",
        return_value=[
            (
                "release-notes.yaml",
                "uses: canonical/release-notes-automation/.github/workflows/action.yml@main",
            )
        ],
    )
    mocker.patch(
        "scorers.documentation.logic.repo_releases",
        return_value=[
            {"tag_name": "v1.1.0", "draft": False, "body": "Release notes for v1.1.0"},
            {"tag_name": "v1.0.0", "draft": False, "body": "Initial release notes"},
        ],
    )
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="")
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["release_notes_process_implemented"] is True


def test_release_notes_fails_without_workflow_reference(mocker):
    """Release notes requires canonical workflow reference even with structure."""
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: (
            path
            in {
                "docs/release-notes/common.yaml",
                "docs/release-notes/releases",
                "docs/release-notes/template",
            }
        ),
    )
    mocker.patch(
        "scorers.documentation.logic.workflow_files",
        return_value=[("ci.yaml", "name: CI\nruns: lint")],
    )
    mocker.patch(
        "scorers.documentation.logic.repo_releases",
        return_value=[
            {"tag_name": "v1.1.0", "draft": False, "body": "Release notes for v1.1.0"},
            {"tag_name": "v1.0.0", "draft": False, "body": "Initial release notes"},
        ],
    )
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="")
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["release_notes_process_implemented"] is False


def test_uses_rtd_hosting_requires_explicit_signal(mocker):
    """Ensure generic textual mentions don't trigger RTD hosting detection."""
    unit = EvaluationUnit(
        product_id="matrix",
        product_type=ProductType.CHARM,
        repo="canonical/synapse-operator",
        documentation_url="",
    )
    mocker.patch("scorers.documentation.logic.repo_file_exists", return_value=True)
    # README contains a generic mention but no URL or badge
    mocker.patch(
        "scorers.documentation.logic.repo_file_text",
        return_value=(
            "This project mentions ReadTheDocs in the README but provides no URL or badge: "
            "ReadTheDocs is great"
        ),
    )
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])

    result = compute_metrics(unit, "gh-token", "or-key")
    assert result["uses_rtd_hosting"] is False


def test_uses_rtd_hosting_detects_rtd_hosted_patterns(mocker):
    """Detect common readthedocs-hosted.com badge/image and URL patterns."""
    unit = EvaluationUnit(
        product_id="matrix",
        product_type=ProductType.CHARM,
        repo="canonical/synapse-operator",
        documentation_url="",
    )
    mocker.patch("scorers.documentation.logic.repo_file_exists", return_value=True)
    # README contains a variety of explicit RTD-hosted URLs and badges
    mocker.patch(
        "scorers.documentation.logic.repo_file_text",
        return_value=(
            "![Documentation Status](https://canonical.synapse.readthedocs-hosted.com/_static/readthedocs-badge.svg)\n"
            "Visit the docs: https://canonical.synapse.readthedocs-hosted.com/\n"
            '<img src="https://readthedocs.io/projects/myproj/badge/icon" '
            'alt="Read the Docs" />\n'
        ),
    )
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])

    result = compute_metrics(unit, "gh-token", "or-key")
    assert result["uses_rtd_hosting"] is True


def test_readme_and_contributing_presence_only_requires_non_empty_files(mocker):
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: path in {"README.md", "CONTRIBUTING.md"},
    )
    mocker.patch(
        "scorers.documentation.logic.repo_file_text",
        side_effect=lambda repo, path, token: {
            "README.md": "# Project\n\n{{ cookiecutter.project_name }}\n\n## Overview\n",
            "CONTRIBUTING.md": "# Contributing\n\n<!-- TODO: replace this file -->\n",
        }.get(path, ""),
    )
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["readme_present"] is True
    assert result["contributing_present"] is True
    assert result["has_security"] is False


def test_diataxis_ai_metric_uses_openrouter_result(mocker):
    """AI Diataxis metric should parse OpenRouter JSON response."""
    fake_client = mocker.Mock()
    fake_client.chat.completions.create.return_value = mocker.Mock(
        choices=[
            mocker.Mock(
                message=mocker.Mock(content='{"diataxis_coverage": 3, "reasoning": "has 3 types"}')
            )
        ]
    )
    mocker.patch("scorers.documentation.logic.OpenAI", return_value=fake_client)
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="# Docs")
    mocker.patch("scorers.documentation.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "or-key", model="openrouter/test-model")
    assert result["diataxis_coverage_ai"] == 3


def test_diataxis_ai_metric_falls_back_to_zero_when_api_key_missing(mocker):
    """AI Diataxis metric should return 0 when API key is missing."""
    mocker.patch("scorers.documentation.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="")
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "", model="openrouter/test-model")
    assert result["diataxis_coverage_ai"] == 0


def test_diataxis_ai_metric_clamps_to_0_4_range(mocker):
    """AI Diataxis metric should clamp results to 0-4 range."""
    fake_client = mocker.Mock()
    # Test with out-of-range value (should clamp to 4)
    fake_client.chat.completions.create.return_value = mocker.Mock(
        choices=[
            mocker.Mock(message=mocker.Mock(content='{"diataxis_coverage": 10, "reasoning": ""}'))
        ]
    )
    mocker.patch("scorers.documentation.logic.OpenAI", return_value=fake_client)
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="# Docs")
    mocker.patch("scorers.documentation.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "or-key", model="openrouter/test-model")
    assert result["diataxis_coverage_ai"] == 4


def test_has_changelog_true_when_file_exists(mocker):
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: path == "CHANGELOG.md",
    )
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="")
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "")
    assert result["has_changelog"] is True


def test_has_changelog_false_when_file_missing(mocker):
    mocker.patch("scorers.documentation.logic.repo_file_exists", return_value=False)
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="")
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])
    mocker.patch("scorers.documentation.logic.workflow_files", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "")
    assert result["has_changelog"] is False
