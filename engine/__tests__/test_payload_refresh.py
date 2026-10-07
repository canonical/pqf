import json

from engine.framework import contract_digest, discover_frameworks
from engine.workflow_matrix import stale_live_versions


def test_scalar_payload_cannot_be_carried_forward_even_if_contract_matches(tmp_path):
    from pathlib import Path

    frameworks = discover_frameworks(Path(__file__).resolve().parents[2] / "framework/versions")
    for framework in frameworks:
        folder = tmp_path / "versions" / framework.id
        folder.mkdir(parents=True)
        (folder / "portfolio.json").write_text(
            json.dumps(
                {
                    "contract_digest": contract_digest(framework),
                    "products": [],
                }
            )
        )
    assert [f.id for f in stale_live_versions(frameworks, tmp_path)] == ["v0", "v1"]
