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
) -> None:
    version_dir = root / version_id
    version_dir.mkdir(parents=True)
    (version_dir / "framework.yaml").write_text(
        yaml.safe_dump(
            {
                "id": version_id,
                "sequence": sequence,
                "label": f"PQF {version_id.upper()}",
                "status": status,
                "description": f"{version_id} contract",
            },
            sort_keys=False,
        )
    )
    (version_dir / "dimensions.yaml").write_text(
        yaml.safe_dump(
            {
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


def _write_portfolio(public_dir: Path, version_id: str, *, digest: str, generated_at: str) -> None:
    path = public_dir / "versions" / version_id / "portfolio.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "framework": {"id": version_id},
                "generated_at": generated_at,
                "contract_digest": digest,
            }
        )
    )


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
