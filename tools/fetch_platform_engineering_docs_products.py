#!/usr/bin/env python3
"""Temporary migration helper that fetches platform-engineering-docs products.

This script exists only to support the one-time catalog discovery / migration
workflow. Once the docs-to-PQF transition is complete, this helper and the
Makefile fetch target can be removed cleanly.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path


def _has_yaml_files(path: Path) -> bool:
    return any(path.glob("*.yaml")) or any(path.glob("*.yml"))


def _load_listing(repo: str, ref: str) -> list[dict]:
    endpoint = f"repos/{repo}/contents/data/products"
    if ref:
        endpoint += f"?ref={ref}"
    output = subprocess.check_output(["gh", "api", endpoint], text=True)
    return json.loads(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch docs product YAMLs")
    parser.add_argument("--repo", default="canonical/platform-engineering-docs")
    parser.add_argument("--ref", default="main")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if _has_yaml_files(output_dir):
        return 0

    try:
        listing = _load_listing(args.repo, args.ref)
        for item in listing:
            if item.get("type") != "file":
                continue
            name = item.get("name", "")
            if not name.endswith((".yaml", ".yml")):
                continue
            if name in {"schema.yaml", "template.yaml"}:
                continue
            path = item.get("path")
            if not path:
                continue
            content_json = subprocess.check_output(
                ["gh", "api", f"repos/{args.repo}/contents/{path}?ref={args.ref}"],
                text=True,
            )
            payload = json.loads(content_json)
            encoded = payload.get("content", "")
            if not encoded:
                continue
            data = base64.b64decode(encoded)
            (output_dir / name).write_bytes(data)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
