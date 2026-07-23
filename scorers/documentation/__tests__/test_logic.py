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
            "docs/release-notes.md",
            "docs/tutorial.md",
            "docs/how-to.md",
            "docs/reference.md",
            "docs/explanation.md",
        },
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
            "README.md": (
                "# Synapse\n\n## Overview\n\n## Getting started\n\n## Support\n"
            ),
            "CONTRIBUTING.md": (
                "# Contributing\n\n## Development\n\n## Testing\n\n## Governance\n"
            ),
        }.get(path, ""),
    )

    # Positive examples that SHOULD count as tutorial tests
    positive_names = [
        "tutorial tests",
        "tutorial e2e tests",
        "tutorial verification",
    ]

    for name in positive_names:
        mocker.patch(
            "scorers.documentation.logic.default_branch_check_runs",
            return_value=[
                {"name": "docs lint", "conclusion": "success"},
                {"name": "vale", "conclusion": "success"},
                {"name": "link check", "conclusion": "success"},
                {"name": "docs build", "conclusion": "success"},
                {"name": name, "conclusion": "success"},
            ],
        )
        result = compute_metrics(UNIT, "gh-token", "or-key", model="openrouter/test-model")
        assert result["tutorial_tested"] is True

    # Negative examples that should NOT pass
    negative_names = [
        "tutorial build",
        "tutorial lint",
        "docs tutorial",
    ]
    for name in negative_names:
        mocker.patch(
            "scorers.documentation.logic.default_branch_check_runs",
            return_value=[
                {"name": "docs lint", "conclusion": "success"},
                {"name": "vale", "conclusion": "success"},
                {"name": "link check", "conclusion": "success"},
                {"name": "docs build", "conclusion": "success"},
                {"name": name, "conclusion": "success"},
            ],
        )
        result = compute_metrics(UNIT, "gh-token", "or-key", model="openrouter/test-model")
        assert result["tutorial_tested"] is False

    # Generic CI names like 'playwright' alone should NOT count as tutorial tests
    mocker.patch(
        "scorers.documentation.logic.default_branch_check_runs",
        return_value=[
            {"name": "docs lint", "conclusion": "success"},
            {"name": "vale", "conclusion": "success"},
            {"name": "link check", "conclusion": "success"},
            {"name": "docs build", "conclusion": "success"},
            {"name": "playwright", "conclusion": "success"},
        ],
    )
    result2 = compute_metrics(UNIT, "gh-token", "or-key", model="openrouter/test-model")
    assert result2["tutorial_tested"] is False


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


def test_documentation_workflows_use_latest_conclusion(mocker):
    """Ensure workflow pass/fail is determined by the latest conclusion per check-family.

    We simulate multiple check-runs with the same name where a later run fails and expect
    the overall documentation_workflows_passing to be False.
    """
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: path
        in {
            "README.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "docs/tutorial.md",
            "docs/how-to.md",
            "docs/reference.md",
            "docs/explanation.md",
        },
    )
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="# Docs")
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])
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


def test_tutorial_tested_uses_latest_conclusion(mocker):
    """The tutorial_tested metric should reflect the latest matching check-run conclusion.

    If an earlier run succeeded but a later matching tutorial-test run failed, the metric
    must be False. Conversely, a later success should set it True.
    """
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        side_effect=lambda repo, path, token: path
        in {
            "README.md",
            "docs/tutorial.md",
        },
    )
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="# Docs")
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])

    # Later failure should make metric False
    mocker.patch(
        "scorers.documentation.logic.default_branch_check_runs",
        return_value=[
            {
                "name": "tutorial tests",
                "conclusion": "success",
                "completed_at": "2026-01-01T00:00:00Z",
            },
            {
                "name": "tutorial tests",
                "conclusion": "failure",
                "completed_at": "2026-01-02T00:00:00Z",
            },
        ],
    )
    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["tutorial_tested"] is False

    # Later success should make metric True
    mocker.patch(
        "scorers.documentation.logic.default_branch_check_runs",
        return_value=[
            {
                "name": "tutorial tests",
                "conclusion": "failure",
                "completed_at": "2026-01-01T00:00:00Z",
            },
            {
                "name": "tutorial tests",
                "conclusion": "success",
                "completed_at": "2026-01-02T00:00:00Z",
            },
        ],
    )
    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["tutorial_tested"] is True


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
            "<img src=\"https://readthedocs.io/projects/myproj/badge/icon\" "
            "alt=\"Read the Docs\" />\n"
        ),
    )
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])
    mocker.patch("scorers.documentation.logic.repo_releases", return_value=[])

    result = compute_metrics(unit, "gh-token", "or-key")
    assert result["uses_rtd_hosting"] is True


def test_template_like_readme_and_contributing_fail(mocker):
    """Template-like README or CONTRIBUTING should NOT pass structure checks."""
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

    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["readme_meets_structure"] is False
    assert result["contributing_meets_structure"] is False


def test_release_notes_require_process_marker(mocker):
    """If releases have bodies but no process marker file, the metric should be False."""
    # No known marker files present
    mocker.patch(
        "scorers.documentation.logic.repo_file_exists",
        return_value=False,
    )
    # Two non-draft releases with bodies
    mocker.patch(
        "scorers.documentation.logic.repo_releases",
        return_value=[
            {"tag_name": "v1.2.0", "draft": False, "body": "Notes for v1.2.0"},
            {"tag_name": "v1.1.0", "draft": False, "body": "Notes for v1.1.0"},
        ],
    )
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="")
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["recent_release_notes_present"] is False


def test_release_notes_with_marker_and_bodies_pass(mocker):
    """Process marker + latest two non-draft releases with bodies should pass."""
    # Simulate presence of a known marker file
    def exists(repo, path, token):
        return path in {"docs/release-notes.md", "README.md"}

    mocker.patch("scorers.documentation.logic.repo_file_exists", side_effect=exists)
    mocker.patch(
        "scorers.documentation.logic.repo_releases",
        return_value=[
            {"tag_name": "v2.0.0", "draft": False, "body": "Notes for v2.0.0"},
            {"tag_name": "v1.9.0", "draft": False, "body": "Notes for v1.9.0"},
        ],
    )
    mocker.patch("scorers.documentation.logic.repo_file_text", return_value="")
    mocker.patch("scorers.documentation.logic.default_branch_check_runs", return_value=[])

    result = compute_metrics(UNIT, "gh-token", "or-key")
    assert result["recent_release_notes_present"] is True
