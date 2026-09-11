#!/usr/bin/env python3
"""engagement scorer compatibility wrapper."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scorers.run import main as run_main  # noqa: E402


def main() -> int:
    return run_main(fixed_dimension="engagement")


if __name__ == "__main__":
    sys.exit(main())
