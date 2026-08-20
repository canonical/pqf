# Documentation and SSDLC Calibration Design

## Goal

Calibrate the documentation and SSDLC dimensions so PQF starts with a small, high-confidence core that teams can trust for planning, while still showcasing one AI-assisted metric.

## Problem statement

Documentation and SSDLC currently mix strong deterministic checks with immature or loosely-scoped signals, which weakens medal credibility:
- release-notes scoring does not yet prove the Canonical release-notes workflow is actually implemented,
- documentation maturity is too coarse and tends to collapse toward bronze/below minimum,
- SSDLC has good baseline signals but is missing a simple high-value control (signed commits),
- AI-assisted scoring is not currently represented in a clear showcase role.

## Scope

In scope:
- tighten documentation release-notes detection to deterministic process evidence,
- remove tutorial-testing signal for now,
- keep RTD hosting informational,
- reintroduce AI-assisted Diataxis as an informational showcase metric,
- add signed-commit enforcement as an SSDLC metric,
- rebalance documentation and SSDLC tier gating.

Out of scope:
- broad expansion of new metrics beyond this calibrated core set,
- UI behavior changes,
- changes to dimensions outside documentation and SSDLC.

## Design

### 1. Documentation dimension

Keep the baseline deterministic foundation:
- `readme_present`
- `contributing_present`
- `has_security`

Replace weak release-notes inference with explicit process evidence:
- rename metric intent to `release_notes_process_implemented`,
- require workflow evidence referencing canonical release-notes automation (generation workflow, and optionally PR compliance workflow),
- require expected release-notes repository structure under `docs/release-notes/` (common file, artifacts/releases/templates layout),
- require recent release notes evidence (for example release bodies or generated notes files) when applicable.

Remove:
- `tutorial_tested` (deferred until a clearer, fleet-wide standard exists).

Keep informational-only:
- `uses_rtd_hosting` (because subproducts may intentionally inherit root-product docs),
- `diataxis_coverage_ai` as the AI-assisted showcase signal.

### 2. AI Diataxis showcase behavior

Reintroduce an AI-assisted Diataxis metric as informational-only from day one:
- it is visible in outputs and UI,
- it does not gate medal levels yet,
- it is clearly labeled as AI-assisted evidence.

Rationale:
- provides a concrete showcase of PQF’s AI scoring machinery,
- avoids early gating risk while prompts and confidence semantics mature,
- preserves deterministic medal trust.

### 3. Documentation medal tiers

Calibrate tiers to improve spread while remaining simple:
- **Bronze**: `readme_present`, `contributing_present`, `has_security`
- **Silver**: Bronze + `release_notes_process_implemented`
- **Gold**: Silver + `documentation_workflows_passing`

Informational-only in all tiers:
- `uses_rtd_hosting`
- `diataxis_coverage_ai`

### 4. SSDLC dimension

Keep current deterministic baseline signals:
- `renovate_enabled`
- `repo_automation_registered`
- branch-protection and required-check controls
- existing SAST/CVE signals

Add:
- `signed_commits_required` derived from branch protection signature enforcement (`required_signatures.enabled` equivalent repository signal).

Do not duplicate:
- `SECURITY.md` in SSDLC (already represented in Documentation baseline).

### 5. SSDLC medal tiers

Use incremental enforcement:
- **Bronze**: Renovate + repo automation registration
- **Silver**: Bronze + branch protection / required checks
- **Gold**: Silver + signed commits + security workflow/CVE controls

## Data flow and error handling

- Scorers continue using deterministic repository/workflow/API evidence.
- Missing API fields or missing branch-protection support should resolve to explicit metric false values, not implicit passes.
- AI Diataxis scoring failures should surface as unavailable informational output (not medal-impacting).

## Validation

The calibration is correct when:
- documentation release-notes metric only passes with real process evidence,
- tutorial-tested metric is removed from scorer/config/tests,
- AI Diataxis metric is present and explicitly informational,
- SSDLC exposes signed-commit enforcement,
- medal outputs shift according to new bronze/silver/gold definitions without UI-only overrides.

## Testing

Minimum validation:
- documentation scorer unit tests for release-notes process detection and tutorial metric removal,
- documentation AI-metric tests for informational-only behavior,
- SSDLC scorer unit tests for signed-commit detection,
- targeted engine tests proving medal thresholds match updated `config/dimensions.yaml`.
