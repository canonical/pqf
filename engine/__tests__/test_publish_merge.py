import json
from pathlib import Path

from engine.publish_merge import merge_latest_versions


def _write_portfolio(
    root: Path,
    version: str,
    *,
    source_revision: str,
    contract_digest: str = "digest",
    generated_at: str,
) -> None:
    version_dir = root / "versions" / version
    version_dir.mkdir(parents=True)
    (version_dir / "portfolio.json").write_text(
        json.dumps(
            {
                "framework": {"id": version},
                "source_revision": source_revision,
                "contract_digest": contract_digest,
                "generated_at": generated_at,
            }
        )
    )


def test_merge_replaces_unselected_version_with_latest_published_copy(tmp_path):
    candidate = tmp_path / "candidate"
    latest = tmp_path / "latest"
    _write_portfolio(
        candidate,
        "v1",
        source_revision="new-main",
        generated_at="2026-09-14T01:00:00+00:00",
    )
    _write_portfolio(
        latest,
        "v1",
        source_revision="published-main",
        generated_at="2026-09-14T02:00:00+00:00",
    )

    merge_latest_versions(candidate, latest, selected_versions=set())

    merged = json.loads((candidate / "versions/v1/portfolio.json").read_text())
    assert merged["source_revision"] == "published-main"


def test_merge_keeps_newer_same_identity_copy_for_selected_version(tmp_path):
    candidate = tmp_path / "candidate"
    latest = tmp_path / "latest"
    _write_portfolio(
        candidate,
        "v1",
        source_revision="same-main",
        generated_at="2026-09-14T01:00:00+00:00",
    )
    _write_portfolio(
        latest,
        "v1",
        source_revision="same-main",
        generated_at="2026-09-14T02:00:00+00:00",
    )

    merge_latest_versions(candidate, latest, selected_versions={"v1"})

    merged = json.loads((candidate / "versions/v1/portfolio.json").read_text())
    assert merged["generated_at"] == "2026-09-14T02:00:00+00:00"


def test_merge_keeps_selected_copy_when_scoring_identity_differs(tmp_path):
    candidate = tmp_path / "candidate"
    latest = tmp_path / "latest"
    _write_portfolio(
        candidate,
        "v1",
        source_revision="new-main",
        generated_at="2026-09-14T01:00:00+00:00",
    )
    _write_portfolio(
        latest,
        "v1",
        source_revision="old-main",
        generated_at="2026-09-14T02:00:00+00:00",
    )

    merge_latest_versions(candidate, latest, selected_versions={"v1"})

    merged = json.loads((candidate / "versions/v1/portfolio.json").read_text())
    assert merged["source_revision"] == "new-main"
