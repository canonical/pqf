from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from engine.framework import FrameworkStatus, contract_digest, discover_frameworks


def _portfolio_path(public_dir: Path, version_id: str) -> Path:
    return public_dir / "versions" / version_id / "portfolio.json"


def _load_portfolio(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid portfolio JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Portfolio {path} must be a JSON object")
    return payload


def build_version_index(frameworks, public_dir: Path) -> dict[str, list[dict[str, Any]]]:
    versions: list[dict[str, Any]] = []
    public_dir = Path(public_dir)

    for framework in frameworks:
        portfolio_path = _portfolio_path(public_dir, framework.id)
        if not portfolio_path.exists():
            if framework.status == FrameworkStatus.ARCHIVED:
                continue
            raise ValueError(f"Missing portfolio for framework version {framework.id}")

        portfolio = _load_portfolio(portfolio_path)
        if portfolio.get("framework", {}).get("id") != framework.id:
            raise ValueError(f"{portfolio_path} does not match framework version {framework.id}")

        expected_digest = contract_digest(framework)
        if portfolio.get("contract_digest") != expected_digest:
            raise ValueError(f"{portfolio_path} has a contract digest mismatch")

        versions.append(
            {
                "id": framework.id,
                "sequence": framework.sequence,
                "label": framework.label,
                "status": framework.status.value,
                "description": framework.description,
                "portfolio_url": f"versions/{framework.id}/portfolio.json",
                "generated_at": portfolio["generated_at"],
                "contract_digest": expected_digest,
            }
        )

    return {"versions": versions}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the public framework version index.")
    parser.add_argument("--framework-root", required=True)
    parser.add_argument("--public-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        index = build_version_index(
            discover_frameworks(Path(args.framework_root)),
            Path(args.public_dir),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(index, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
