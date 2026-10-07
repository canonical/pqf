from pathlib import Path

import yaml


def test_compute_job_uses_cross_repository_read_token():
    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / ".github/workflows/compute-metrics.yml").read_text()
    )
    step = next(
        step
        for step in workflow["jobs"]["compute-metrics"]["steps"]
        if step.get("name") == "Run every dimension for selected framework versions"
    )
    assert step["env"]["GITHUB_TOKEN"] == "${{ secrets.PQF_GITHUB_TOKEN }}"
    assert "PQF_GITHUB_TOKEN" in step["run"]
