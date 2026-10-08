import os
import subprocess
from pathlib import Path


def test_score_all_does_not_merge_or_report_success_after_scorer_failure(tmp_path):
    child_make = tmp_path / "child-make"
    child_make.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        "  *score-no-llm*) exit 7 ;;\n"
        '  *) echo "unexpected-generation"; exit 0 ;;\n'
        "esac\n"
    )
    child_make.chmod(0o755)
    result = subprocess.run(
        [
            "make",
            "score-all-no-llm",
            "FRAMEWORK_VERSION=v0",
            "_PRODUCTS=demo",
            f"MAKE={child_make}",
            "GITHUB_TOKEN=test-token",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "unexpected-generation" not in result.stdout
