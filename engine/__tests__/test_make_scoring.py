import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_score_dimension_invokes_only_requested_scorer_without_llm_key():
    result = subprocess.run(
        [
            "make",
            "--dry-run",
            "score-dimension",
            "PRODUCT=traefik-k8s",
            "FRAMEWORK_VERSION=v0",
            "DIMENSION=test_verification",
            "GITHUB_TOKEN=test",
            "OPENROUTER_API_KEY=",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("scorers/run.py") == 1
    assert "--dimension test_verification" in result.stdout
    assert "products/traefik-k8s.yaml" in result.stdout
    assert "--framework-version v0" in result.stdout
    assert ".pqf-score/v0/traefik-k8s/test_verification.json" in result.stdout
    assert "OPENROUTER_API_KEY is not set" not in result.stdout


@pytest.mark.parametrize("missing", ["PRODUCT", "DIMENSION", "FRAMEWORK_VERSION"])
def test_score_dimension_requires_explicit_selection(missing):
    variables = {
        "PRODUCT": "traefik-k8s",
        "DIMENSION": "test_verification",
        "FRAMEWORK_VERSION": "v0",
    }
    result = subprocess.run(
        [
            "make",
            "--dry-run",
            "score-dimension",
            "GITHUB_TOKEN=test",
            *(f"{key}={value}" for key, value in variables.items() if key != missing),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert f"{missing} is required" in result.stderr
