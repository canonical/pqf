from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

CATEGORY_TITLES = {
    "metadata_only": "Metadata-only changes",
    "additive_informational": "Additive informational measurements",
    "scoring_semantic": "Scoring-semantic changes",
    "catalog_membership_or_target": "Catalog membership or target changes",
}


def _empty_change_buckets() -> dict[str, list[str]]:
    return {category: [] for category in CATEGORY_TITLES}


def _validate_snapshot_roots(
    snapshot: dict[str, Any],
    *,
    framework_source: str,
    products_source: str,
) -> None:
    if not snapshot["frameworks"]:
        raise ValueError(f"Missing required framework snapshot root: {framework_source}")
    if not snapshot["products"]:
        raise ValueError(f"Missing required product catalog snapshot root: {products_source}")


def _load_yaml_text(text: str, source: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {source}")
    return data


def _framework_version_dirs(framework_root: Path) -> list[Path]:
    if not framework_root.exists():
        return []
    return sorted(path for path in framework_root.iterdir() if path.is_dir())


def _read_worktree_snapshot(
    framework_root: Path = Path("framework/versions"),
    products_dir: Path = Path("products"),
) -> dict[str, Any]:
    snapshot = {"frameworks": {}, "products": {}}

    for version_dir in _framework_version_dirs(framework_root):
        metadata_path = version_dir / "framework.yaml"
        dimensions_path = version_dir / "dimensions.yaml"
        if not metadata_path.exists():
            raise ValueError(f"Missing required framework snapshot file: {metadata_path}")
        if not dimensions_path.exists():
            raise ValueError(f"Missing required framework snapshot file: {dimensions_path}")

        version_id = version_dir.name
        snapshot["frameworks"][version_id] = {
            "framework": _load_yaml_text(metadata_path.read_text(), str(metadata_path)),
            "dimensions": _load_yaml_text(dimensions_path.read_text(), str(dimensions_path)),
        }

    for product_path in sorted(products_dir.glob("*.yaml")):
        snapshot["products"][product_path.stem] = _load_yaml_text(
            product_path.read_text(),
            str(product_path),
        )

    _validate_snapshot_roots(
        snapshot,
        framework_source=str(framework_root),
        products_source=str(products_dir),
    )
    return snapshot


def _git_command(*args: str) -> str:
    completed = subprocess.run(
        ["git", "--no-pager", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        )
    return completed.stdout


def _read_git_snapshot(base_ref: str) -> dict[str, Any]:
    tracked_paths = _git_command(
        "ls-tree",
        "-r",
        "--name-only",
        base_ref,
        "--",
        "framework/versions",
        "products",
    ).splitlines()

    snapshot = {"frameworks": {}, "products": {}}
    for raw_path in tracked_paths:
        path = PurePosixPath(raw_path)
        if path.parts[:2] == ("framework", "versions") and path.name in {
            "framework.yaml",
            "dimensions.yaml",
        }:
            version_id = path.parts[2]
            entry = snapshot["frameworks"].setdefault(version_id, {})
            snapshot_key = "framework" if path.name == "framework.yaml" else "dimensions"
            entry[snapshot_key] = _load_yaml_text(
                _git_command("show", f"{base_ref}:{raw_path}"),
                f"{base_ref}:{raw_path}",
            )
        elif len(path.parts) == 2 and path.parts[0] == "products" and path.suffix == ".yaml":
            snapshot["products"][path.stem] = _load_yaml_text(
                _git_command("show", f"{base_ref}:{raw_path}"),
                f"{base_ref}:{raw_path}",
            )

    for version_id, entry in snapshot["frameworks"].items():
        if "framework" not in entry:
            raise ValueError(
                "Missing required framework snapshot file: "
                f"{base_ref}:framework/versions/{version_id}/framework.yaml"
            )
        if "dimensions" not in entry:
            raise ValueError(
                "Missing required framework snapshot file: "
                f"{base_ref}:framework/versions/{version_id}/dimensions.yaml"
            )

    _validate_snapshot_roots(
        snapshot,
        framework_source=f"{base_ref}:framework/versions",
        products_source=f"{base_ref}:products",
    )
    return snapshot


def _is_additive_informational_output(output_config: dict[str, Any]) -> bool:
    return bool(output_config.get("informational"))


def _record_change(changes: dict[str, list[str]], category: str, message: str) -> None:
    changes[category].append(message)


def _compare_framework_metadata(
    version_id: str,
    base_metadata: dict[str, Any],
    head_metadata: dict[str, Any],
    changes: dict[str, list[str]],
) -> None:
    metadata_fields = [
        field
        for field in ("label", "description")
        if base_metadata.get(field) != head_metadata.get(field)
    ]
    if metadata_fields:
        _record_change(
            changes,
            "metadata_only",
            f"framework {version_id} metadata changed: {', '.join(metadata_fields)}",
        )

    semantic_fields = [
        field
        for field in ("sequence", "status")
        if base_metadata.get(field) != head_metadata.get(field)
    ]
    for field in semantic_fields:
        _record_change(
            changes,
            "scoring_semantic",
            f"framework {version_id} changed {field}",
        )


def _compare_output(
    version_id: str,
    dimension_name: str,
    output_key: str,
    base_output: dict[str, Any] | None,
    head_output: dict[str, Any] | None,
    changes: dict[str, list[str]],
) -> None:
    prefix = f"framework {version_id} dimension {dimension_name} output {output_key}"
    if base_output is None and head_output is not None:
        category = (
            "additive_informational"
            if _is_additive_informational_output(head_output)
            else "scoring_semantic"
        )
        message = (
            "framework "
            f"{version_id} dimension {dimension_name} added informational output {output_key}"
            if category == "additive_informational"
            else f"framework {version_id} dimension {dimension_name} added output {output_key}"
        )
        _record_change(changes, category, message)
        return
    if base_output is not None and head_output is None:
        _record_change(
            changes,
            "scoring_semantic",
            f"framework {version_id} dimension {dimension_name} removed output {output_key}",
        )
        return
    if base_output is None or head_output is None:
        return

    if base_output.get("implementation") != head_output.get("implementation"):
        _record_change(changes, "scoring_semantic", f"{prefix} changed implementation")
    if base_output.get("type") != head_output.get("type"):
        _record_change(changes, "scoring_semantic", f"{prefix} changed type")
    if bool(base_output.get("informational")) != bool(head_output.get("informational")):
        _record_change(changes, "scoring_semantic", f"{prefix} changed informational")

    metadata_fields = [
        field
        for field in ("label", "description", "range", "ai_assisted")
        if base_output.get(field) != head_output.get(field)
    ]
    if metadata_fields:
        _record_change(
            changes,
            "metadata_only",
            f"{prefix} metadata changed: {', '.join(metadata_fields)}",
        )


def _compare_dimension(
    version_id: str,
    dimension_name: str,
    base_dimension: dict[str, Any],
    head_dimension: dict[str, Any],
    changes: dict[str, list[str]],
) -> None:
    metadata_fields = [
        field
        for field in ("label", "description")
        if base_dimension.get(field) != head_dimension.get(field)
    ]
    if metadata_fields:
        _record_change(
            changes,
            "metadata_only",
            "framework "
            f"{version_id} dimension {dimension_name} metadata changed: "
            f"{', '.join(metadata_fields)}",
        )

    semantic_mapping = {
        "scorer": "changed scorer",
        "applies_to": "changed applies_to",
        "aggregation": "changed aggregation",
        "required_metrics_for_scoring": "changed required metrics",
        "medals": "changed medal criteria",
    }
    for field, message in semantic_mapping.items():
        if base_dimension.get(field) != head_dimension.get(field):
            _record_change(
                changes,
                "scoring_semantic",
                f"framework {version_id} dimension {dimension_name} {message}",
            )

    base_outputs = base_dimension.get("outputs", {})
    head_outputs = head_dimension.get("outputs", {})
    output_keys = sorted(set(base_outputs) | set(head_outputs))
    for output_key in output_keys:
        _compare_output(
            version_id,
            dimension_name,
            output_key,
            base_outputs.get(output_key),
            head_outputs.get(output_key),
            changes,
        )


def _compare_frameworks(
    base_frameworks: dict[str, Any],
    head_frameworks: dict[str, Any],
    changes: dict[str, list[str]],
) -> None:
    version_ids = sorted(set(base_frameworks) | set(head_frameworks))
    for version_id in version_ids:
        base_entry = base_frameworks.get(version_id)
        head_entry = head_frameworks.get(version_id)
        if base_entry is None:
            _record_change(changes, "scoring_semantic", f"framework {version_id} added")
            continue
        if head_entry is None:
            _record_change(changes, "scoring_semantic", f"framework {version_id} removed")
            continue

        _compare_framework_metadata(
            version_id,
            base_entry["framework"],
            head_entry["framework"],
            changes,
        )

        base_dimensions = base_entry["dimensions"].get("dimensions", {})
        head_dimensions = head_entry["dimensions"].get("dimensions", {})
        dimension_names = sorted(set(base_dimensions) | set(head_dimensions))
        for dimension_name in dimension_names:
            base_dimension = base_dimensions.get(dimension_name)
            head_dimension = head_dimensions.get(dimension_name)
            if base_dimension is None:
                _record_change(
                    changes,
                    "scoring_semantic",
                    f"framework {version_id} added dimension {dimension_name}",
                )
                continue
            if head_dimension is None:
                _record_change(
                    changes,
                    "scoring_semantic",
                    f"framework {version_id} removed dimension {dimension_name}",
                )
                continue
            _compare_dimension(version_id, dimension_name, base_dimension, head_dimension, changes)


def _compare_product(
    product_id: str,
    base_product: dict[str, Any],
    head_product: dict[str, Any],
    changes: dict[str, list[str]],
) -> None:
    metadata_fields = [
        field
        for field in ("name", "description", "lifecycle", "ownership", "context_refs")
        if base_product.get(field) != head_product.get(field)
    ]
    if metadata_fields:
        _record_change(
            changes,
            "metadata_only",
            f"product {product_id} metadata changed: {', '.join(metadata_fields)}",
        )

    for field in ("source", "documentation_url", "allure_report_url"):
        if base_product.get(field) != head_product.get(field):
            _record_change(
                changes,
                "scoring_semantic",
                f"product {product_id} changed {field}",
            )

    membership_fields = {
        "introduced_in": "changed introduction boundary",
        "retired_in": "changed retirement boundary",
        "targets": "changed targets",
        "composed_of": "changed composition",
        "product_type": "changed product_type",
    }
    for field, message in membership_fields.items():
        if base_product.get(field) != head_product.get(field):
            _record_change(
                changes,
                "catalog_membership_or_target",
                f"product {product_id} {message}",
            )


def _compare_products(
    base_products: dict[str, Any],
    head_products: dict[str, Any],
    changes: dict[str, list[str]],
) -> None:
    product_ids = sorted(set(base_products) | set(head_products))
    for product_id in product_ids:
        base_product = base_products.get(product_id)
        head_product = head_products.get(product_id)
        if base_product is None:
            _record_change(changes, "catalog_membership_or_target", f"product {product_id} added")
            continue
        if head_product is None:
            _record_change(
                changes,
                "catalog_membership_or_target",
                f"product {product_id} removed",
            )
            continue
        _compare_product(product_id, base_product, head_product, changes)


def classify_repository_changes(
    base: dict[str, Any],
    head: dict[str, Any],
) -> dict[str, list[str]]:
    changes = _empty_change_buckets()
    _compare_frameworks(base.get("frameworks", {}), head.get("frameworks", {}), changes)
    _compare_products(base.get("products", {}), head.get("products", {}), changes)
    return {category: sorted(entries) for category, entries in changes.items()}


def render_change_report(changes: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for category, title in CATEGORY_TITLES.items():
        lines.append(f"## {title}")
        entries = changes.get(category, [])
        if entries:
            lines.extend(f"- {entry}" for entry in entries)
        else:
            lines.append("- None.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize semantic source changes across PQF contracts."
    )
    parser.add_argument("--base-ref", required=True, help="Git revision to compare against.")
    args = parser.parse_args(argv)

    try:
        base_snapshot = _read_git_snapshot(args.base_ref)
        head_snapshot = _read_worktree_snapshot()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(render_change_report(classify_repository_changes(base_snapshot, head_snapshot)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
