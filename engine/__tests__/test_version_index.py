import json
from pathlib import Path

import pytest
import yaml

from engine.framework import contract_digest, discover_frameworks
from engine.version_index import build_version_index


def _write_framework_version(
    root: Path,
    *,
    version_id: str,
    sequence: int,
    status: str,
    label: str | None = None,
    description: str | None = None,
    dimensions: dict | None = None,
) -> None:
    version_dir = root / version_id
    version_dir.mkdir(parents=True)
    (version_dir / "framework.yaml").write_text(
        yaml.safe_dump(
            {
                "id": version_id,
                "sequence": sequence,
                "label": label or f"PQF {version_id.upper()}",
                "status": status,
                "description": description or f"{version_id} contract",
            },
            sort_keys=False,
        )
    )
    (version_dir / "dimensions.yaml").write_text(
        yaml.safe_dump(
            dimensions
            or {
                "dimensions": {
                    "test_verification": {
                        "label": "Test verification",
                        "description": "Automated test health.",
                        "scorer": "scorers/test_verification/scorer.py",
                        "outputs": {
                            "latest_build_passing": {
                                "implementation": "latest-build-passing/v1",
                                "type": "boolean",
                                "label": "Latest build passing",
                                "description": "Latest CI summary has no failures.",
                            }
                        },
                        "medals": {"bronze": ["latest_build_passing == true"]},
                    }
                }
            },
            sort_keys=False,
        )
    )


def _write_portfolio(
    public_dir: Path,
    version_id: str,
    *,
    digest: str,
    generated_at: str,
    extra: dict | None = None,
) -> None:
    path = public_dir / "versions" / version_id / "portfolio.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "framework": {"id": version_id},
        "generated_at": generated_at,
        "contract_digest": digest,
    }
    payload.update(extra or {})
    path.write_text(json.dumps(payload))


def test_build_version_index_includes_active_upcoming_and_existing_archived_versions(tmp_path):
    framework_root = tmp_path / "framework" / "versions"
    _write_framework_version(framework_root, version_id="v0", sequence=0, status="archived")
    _write_framework_version(framework_root, version_id="v1", sequence=1, status="active")
    _write_framework_version(framework_root, version_id="v2", sequence=2, status="upcoming")

    frameworks = discover_frameworks(framework_root)
    public_dir = tmp_path / "public"

    for framework in frameworks:
        if framework.status != "archived" or framework.id == "v0":
            _write_portfolio(
                public_dir,
                framework.id,
                digest=contract_digest(framework),
                generated_at=f"2026-01-0{framework.sequence + 1}T00:00:00+00:00",
            )

    index = build_version_index(frameworks, public_dir)

    assert index == {
        "versions": [
            {
                "id": "v0",
                "sequence": 0,
                "label": "PQF V0",
                "status": "archived",
                "description": "v0 contract",
                "portfolio_url": "versions/v0/portfolio.json",
                "generated_at": "2026-01-01T00:00:00+00:00",
                "contract_digest": contract_digest(frameworks[0]),
            },
            {
                "id": "v1",
                "sequence": 1,
                "label": "PQF V1",
                "status": "active",
                "description": "v1 contract",
                "portfolio_url": "versions/v1/portfolio.json",
                "generated_at": "2026-01-02T00:00:00+00:00",
                "contract_digest": contract_digest(frameworks[1]),
            },
            {
                "id": "v2",
                "sequence": 2,
                "label": "PQF V2",
                "status": "upcoming",
                "description": "v2 contract",
                "portfolio_url": "versions/v2/portfolio.json",
                "generated_at": "2026-01-03T00:00:00+00:00",
                "contract_digest": contract_digest(frameworks[2]),
            },
        ]
    }


def test_build_version_index_requires_active_and_upcoming_portfolios(tmp_path):
    framework_root = tmp_path / "framework" / "versions"
    _write_framework_version(framework_root, version_id="v0", sequence=0, status="active")
    _write_framework_version(framework_root, version_id="v1", sequence=1, status="upcoming")

    frameworks = discover_frameworks(framework_root)
    public_dir = tmp_path / "public"
    _write_portfolio(
        public_dir,
        "v0",
        digest=contract_digest(frameworks[0]),
        generated_at="2026-01-01T00:00:00+00:00",
    )

    with pytest.raises(ValueError, match="Missing portfolio for framework version v1"):
        build_version_index(frameworks, public_dir)


def test_build_version_index_rejects_digest_mismatches(tmp_path):
    framework_root = tmp_path / "framework" / "versions"
    _write_framework_version(framework_root, version_id="v0", sequence=0, status="active")
    _write_framework_version(framework_root, version_id="v1", sequence=1, status="upcoming")

    frameworks = discover_frameworks(framework_root)
    public_dir = tmp_path / "public"
    _write_portfolio(
        public_dir,
        "v0",
        digest="wrong",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    _write_portfolio(
        public_dir,
        "v1",
        digest=contract_digest(frameworks[1]),
        generated_at="2026-01-02T00:00:00+00:00",
    )

    with pytest.raises(ValueError, match="contract digest mismatch"):
        build_version_index(frameworks, public_dir)


# ── Archive policy: frozen measurements, migratable payload format ────────────


def _catalog(tmp_path: Path, name: str, versions: list[dict]) -> list:
    root = tmp_path / name / "framework" / "versions"
    for version in versions:
        _write_framework_version(root, **version)
    return discover_frameworks(root)


def test_activation_to_archived_keeps_the_recorded_contract_digest_valid(tmp_path):
    """Lifecycle metadata is not part of the scoring contract, so freezing is a no-op."""
    live = _catalog(
        tmp_path,
        "live",
        [
            {"version_id": "v0", "sequence": 0, "status": "active", "label": "PQF V0"},
            {"version_id": "v1", "sequence": 1, "status": "upcoming"},
        ],
    )
    public_dir = tmp_path / "public"
    _write_portfolio(
        public_dir,
        "v0",
        digest=contract_digest(live[0]),
        generated_at="2026-01-01T00:00:00+00:00",
    )
    _write_portfolio(
        public_dir,
        "v1",
        digest=contract_digest(live[1]),
        generated_at="2026-01-02T00:00:00+00:00",
    )

    # v0 is archived and relabelled; v1 becomes active. Neither portfolio is rewritten.
    after = _catalog(
        tmp_path,
        "after",
        [
            {
                "version_id": "v0",
                "sequence": 0,
                "status": "archived",
                "label": "PQF V0 (retired)",
                "description": "Frozen 2026 contract.",
            },
            {"version_id": "v1", "sequence": 1, "status": "active"},
        ],
    )

    index = build_version_index(after, public_dir)

    archived_entry = index["versions"][0]
    assert archived_entry["status"] == "archived"
    assert archived_entry["label"] == "PQF V0 (retired)"
    assert archived_entry["contract_digest"] == contract_digest(live[0])
    assert archived_entry["generated_at"] == "2026-01-01T00:00:00+00:00"


def test_archived_portfolio_format_migration_is_accepted(tmp_path):
    """A reviewed schema migration may rewrite the payload if it preserves the record."""
    frameworks = _catalog(
        tmp_path,
        "catalog",
        [
            {"version_id": "v0", "sequence": 0, "status": "archived"},
            {"version_id": "v1", "sequence": 1, "status": "active"},
        ],
    )
    public_dir = tmp_path / "public"
    archived_digest = contract_digest(frameworks[0])
    _write_portfolio(
        public_dir,
        "v0",
        digest=archived_digest,
        generated_at="2026-01-01T00:00:00+00:00",
        extra={
            "schema_version": 2,
            "products": [{"id": "matrix", "grade": "silver"}],
            "compliance_summary": {"at_or_above_target": 1},
        },
    )
    _write_portfolio(
        public_dir,
        "v1",
        digest=contract_digest(frameworks[1]),
        generated_at="2026-02-01T00:00:00+00:00",
    )

    index = build_version_index(frameworks, public_dir)

    assert index["versions"][0] == {
        "id": "v0",
        "sequence": 0,
        "label": "PQF V0",
        "status": "archived",
        "description": "v0 contract",
        "portfolio_url": "versions/v0/portfolio.json",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "contract_digest": archived_digest,
    }


def test_archived_portfolio_is_rejected_when_its_scoring_rules_changed(tmp_path):
    """Digest validation is not relaxed for archives: frozen results cannot be rescored."""
    original = _catalog(
        tmp_path,
        "original",
        [
            {"version_id": "v0", "sequence": 0, "status": "archived"},
            {"version_id": "v1", "sequence": 1, "status": "active"},
        ],
    )
    public_dir = tmp_path / "public"
    _write_portfolio(
        public_dir,
        "v0",
        digest=contract_digest(original[0]),
        generated_at="2026-01-01T00:00:00+00:00",
    )
    _write_portfolio(
        public_dir,
        "v1",
        digest=contract_digest(original[1]),
        generated_at="2026-02-01T00:00:00+00:00",
    )

    rescored = _catalog(
        tmp_path,
        "rescored",
        [
            {
                "version_id": "v0",
                "sequence": 0,
                "status": "archived",
                "dimensions": {
                    "dimensions": {
                        "test_verification": {
                            "label": "Test verification",
                            "description": "Automated test health.",
                            "scorer": "scorers/test_verification/scorer.py",
                            "outputs": {
                                "latest_build_passing": {
                                    "implementation": "latest-build-passing/v2",
                                    "type": "boolean",
                                    "label": "Latest build passing",
                                    "description": "Latest CI summary has no failures.",
                                }
                            },
                            "medals": {"bronze": ["latest_build_passing == true"]},
                        }
                    }
                },
            },
            {"version_id": "v1", "sequence": 1, "status": "active"},
        ],
    )

    with pytest.raises(ValueError, match="contract digest mismatch.*frozen"):
        build_version_index(rescored, public_dir)


def test_build_version_index_requires_generated_at(tmp_path):
    frameworks = _catalog(
        tmp_path, "catalog", [{"version_id": "v0", "sequence": 0, "status": "active"}]
    )
    public_dir = tmp_path / "public"
    path = public_dir / "versions" / "v0" / "portfolio.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"framework": {"id": "v0"}, "contract_digest": contract_digest(frameworks[0])})
    )

    with pytest.raises(ValueError, match="missing generated_at"):
        build_version_index(frameworks, public_dir)
