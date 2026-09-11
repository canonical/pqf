"""
Merges per-scorer JSON outputs into a versioned computed envelope.

Each scorer writes its dimension metrics to a separate file in scorers-output-dir:
    {dim_name}.json -> {"leaf-id": {"metric": value, ...}, ...}
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


def merge_scorer_outputs(
    *,
    product_id: str,
    scorer_dir: Path,
    dimensions_config: dict[str, Any],
    framework_version: str,
    contract_digest: str,
    implementation_fingerprints: dict[str, str],
) -> dict[str, Any]:
    leaf_metrics: dict[str, dict[str, dict[str, Any]]] = {}

    for dim_name in dimensions_config.get("dimensions", {}):
        path = scorer_dir / f"{dim_name}.json"
        if not path.exists():
            raise ValueError(f"Missing scorer output for dimension {dim_name}")

        try:
            dim_data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

        if not isinstance(dim_data, dict):
            raise ValueError(f"Scorer output {path} must be a JSON object")

        for leaf_id, metrics in dim_data.items():
            if not isinstance(metrics, dict):
                raise ValueError(f"Scorer output {path} entry {leaf_id!r} must be a JSON object")
            leaf_metrics.setdefault(leaf_id, {})[dim_name] = metrics

    return {
        "framework_version": framework_version,
        "contract_digest": contract_digest,
        "implementation_fingerprints": implementation_fingerprints,
        "product_id": product_id,
        "computed_at": datetime.now(UTC).isoformat(),
        "leaf_metrics": leaf_metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge scorer outputs into computed JSON")
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--scorers-output-dir", required=True)
    parser.add_argument("--dimensions", required=True)
    parser.add_argument("--framework-version", required=True)
    parser.add_argument("--contract-digest", required=True)
    parser.add_argument("--implementation-fingerprints", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    dimensions_config = yaml.safe_load(Path(args.dimensions).read_text())
    scorer_dir = Path(args.scorers_output_dir)
    try:
        implementation_fingerprints = json.loads(args.implementation_fingerprints)
    except json.JSONDecodeError as exc:
        print(f"Invalid implementation fingerprint mapping: {exc}", file=sys.stderr)
        return 1
    if not isinstance(implementation_fingerprints, dict):
        print("Implementation fingerprints must be a JSON object.", file=sys.stderr)
        return 1

    try:
        output = merge_scorer_outputs(
            product_id=args.product_id,
            scorer_dir=scorer_dir,
            dimensions_config=dimensions_config,
            framework_version=args.framework_version,
            contract_digest=args.contract_digest,
            implementation_fingerprints=implementation_fingerprints,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
