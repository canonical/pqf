"""Validate PQF framework snapshots and product catalog files.

Usage:
    python3 -m engine.validate                          # validate framework snapshots + products
    python3 -m engine.validate --framework-root framework/versions
    python3 -m engine.validate --products-dir products
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from engine.framework import FrameworkVersion, discover_frameworks
from engine.graph import build_graph
from engine.rubric import parse_condition
from scorers import registry

_SCHEMAS_DIR = Path(__file__).parent.parent / "config" / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((_SCHEMAS_DIR / name).read_text())


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if isinstance(data, dict):
        return data
    raise ValueError(f"Expected mapping in {path}")


def validate_file(path: Path, schema: dict) -> list[str]:
    """Return a list of human-readable error messages. Empty means valid."""
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        return [f"  (yaml): {exc}"]
    validator = jsonschema.Draft7Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = " > ".join(str(p) for p in err.path) or "(root)"
        errors.append(f"  {loc}: {err.message}")
    return errors


def _prefix_errors(path: Path, errors: list[str]) -> list[str]:
    return [f"{path}: {error.strip()}" for error in errors]


def _framework_version_dirs(framework_root: Path) -> list[Path]:
    if not framework_root.exists():
        return []
    return sorted(path for path in framework_root.iterdir() if path.is_dir())


def _criterion_metric_key(criterion: str) -> str:
    metric_key, _operator, _value = parse_condition(criterion)
    return metric_key


def _validate_dimension_contract(
    framework: FrameworkVersion,
    dimension_name: str,
    dimension_config: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    outputs = dimension_config.get("outputs", {})
    if not isinstance(outputs, dict):
        return errors

    output_keys = set(outputs)
    required_metrics = dimension_config.get("required_metrics_for_scoring", [])
    if isinstance(required_metrics, list):
        for metric_key in required_metrics:
            if metric_key not in output_keys:
                errors.append(
                    f"framework {framework.id} dimension {dimension_name} "
                    f"required_metrics_for_scoring references undeclared output {metric_key!r}"
                )

    medals = dimension_config.get("medals", {})
    if isinstance(medals, dict):
        for criteria in medals.values():
            if not isinstance(criteria, list):
                continue
            for criterion in criteria:
                if not isinstance(criterion, str):
                    continue
                try:
                    metric_key = _criterion_metric_key(criterion)
                except ValueError as exc:
                    errors.append(
                        f"framework {framework.id} dimension {dimension_name} "
                        f"has invalid criterion {criterion!r}: {exc}"
                    )
                    continue
                if metric_key not in output_keys:
                    errors.append(
                        f"framework {framework.id} dimension {dimension_name} "
                        f"criteria reference undeclared output {metric_key!r}"
                    )

    for output_key, output_config in outputs.items():
        if not isinstance(output_config, dict):
            continue
        implementation_id = output_config.get("implementation")
        binding = registry.METRIC_BINDINGS.get(implementation_id)
        if binding is None:
            errors.append(
                f"framework {framework.id} dimension {dimension_name} output {output_key} "
                f"references unknown metric implementation {implementation_id!r}"
            )
            continue
        if binding.dimension != dimension_name:
            errors.append(
                f"framework {framework.id} dimension {dimension_name} output {output_key} "
                f"references implementation {implementation_id!r} for dimension "
                f"{binding.dimension!r}"
            )
        if binding.output_key != output_key:
            errors.append(
                f"framework {framework.id} dimension {dimension_name} output {output_key} "
                f"references implementation {implementation_id!r} for output "
                f"{binding.output_key!r}"
            )
        if binding.runner_key not in registry.RUNNERS:
            errors.append(
                f"framework {framework.id} dimension {dimension_name} output {output_key} "
                f"references implementation {implementation_id!r} with unknown runner "
                f"{binding.runner_key!r}"
            )
    return errors


def _load_product_dicts(products_dir: Path) -> list[dict[str, Any]]:
    return [_read_yaml_mapping(path) for path in sorted(products_dir.glob("*.yaml"))]


def validate_repository(framework_root: Path, products_dir: Path) -> list[str]:
    """Validate framework snapshots and product catalog cross-file relationships."""
    framework_schema = _load_schema("framework.schema.json")
    dimensions_schema = _load_schema("dimensions.schema.json")
    product_schema = _load_schema("product.schema.json")

    errors: list[str] = []
    framework_files_valid = True
    product_files_valid = True

    if not products_dir.is_dir():
        errors.append(f"{products_dir}: missing required products directory")
        product_files_valid = False

    for version_dir in _framework_version_dirs(framework_root):
        metadata_path = version_dir / "framework.yaml"
        dimensions_path = version_dir / "dimensions.yaml"

        if not metadata_path.exists():
            errors.append(f"{metadata_path}: missing required framework snapshot file")
            framework_files_valid = False
        else:
            file_errors = validate_file(metadata_path, framework_schema)
            if file_errors:
                errors.extend(_prefix_errors(metadata_path, file_errors))
                framework_files_valid = False

        if not dimensions_path.exists():
            errors.append(f"{dimensions_path}: missing required framework snapshot file")
            framework_files_valid = False
        else:
            file_errors = validate_file(dimensions_path, dimensions_schema)
            if file_errors:
                errors.extend(_prefix_errors(dimensions_path, file_errors))
                framework_files_valid = False

    for product_path in sorted(products_dir.glob("*.yaml")):
        file_errors = validate_file(product_path, product_schema)
        if file_errors:
            errors.extend(_prefix_errors(product_path, file_errors))
            product_files_valid = False

    if not framework_files_valid:
        return errors

    try:
        frameworks = discover_frameworks(framework_root)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"{framework_root}: {exc}")
        return errors

    for framework in frameworks:
        for dimension_name, dimension_config in framework.dimensions.get("dimensions", {}).items():
            errors.extend(_validate_dimension_contract(framework, dimension_name, dimension_config))

    if not product_files_valid:
        return errors

    try:
        product_dicts = _load_product_dicts(products_dir)
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    for framework in frameworks:
        try:
            build_graph(product_dicts, frameworks, framework)
        except ValueError as exc:
            errors.append(f"framework {framework.id}: {exc}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate PQF framework snapshot YAML files and product catalog sources."
    )
    parser.add_argument(
        "--framework-root",
        default="framework/versions",
        metavar="DIR",
        help="Directory containing framework snapshots (default: framework/versions)",
    )
    parser.add_argument(
        "--products-dir",
        default="products",
        metavar="DIR",
        help="Directory containing product YAMLs (default: products)",
    )
    args = parser.parse_args()

    errors = validate_repository(Path(args.framework_root), Path(args.products_dir))
    if errors:
        for error in errors:
            print(error)
        print("\nValidation failed.")
        return 1

    print("\nAll files valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
