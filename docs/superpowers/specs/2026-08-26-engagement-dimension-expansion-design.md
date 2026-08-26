# Engagement Dimension Expansion Design

**Tracking:** support_engagement expansion and rename  
**Author:** Copilot  
**Date:** 2026-08-26  
**Status:** Design phase

---

## Problem Statement

PQF's current `support_engagement` dimension only captures maintainer-side responsiveness and ownership signals:

- issue triage latency,
- pull request review latency,
- response coverage,
- squad ownership signal,
- Jira sync presence.

That is useful, but it misses a complementary signal: whether a repository is attracting user attention at all. For portfolio discussions, user engagement is informative even when it should not affect medal outcomes.

The immediate opportunity is GitHub repository traffic. GitHub exposes repository page views via the traffic API, but with important constraints:

- the API only provides the last 14 days of traffic, not 30 days,
- access requires repository write permission,
- traffic availability can differ from normal issue/PR readability and must not destabilize scoring.

We want to broaden the dimension into a general `engagement` view without weakening PQF's medal credibility.

## Goal

Rename `support_engagement` to `engagement` and add one informational user-engagement metric from GitHub:

- `repo_views_14d` — total GitHub repository page views over the last 14 days.

The existing maintainer responsiveness metrics remain the only medal-gating signals. The new traffic metric is visible in PQF outputs and UI, but never participates in bronze, silver, or gold criteria.

## Scope

In scope:

- rename the dimension key, label, description, and scorer package from `support_engagement` to `engagement`,
- preserve current medal semantics for maintainer responsiveness,
- add `repo_views_14d` as an informational numeric output,
- fetch repository views from the GitHub traffic API,
- preserve drift continuity across the dimension rename,
- update tests and affected fixture expectations.

Out of scope:

- adding more user-engagement metrics beyond page views,
- changing bronze/silver/gold thresholds,
- introducing AI-assisted engagement metrics,
- redesigning PQF UI behavior beyond what existing metadata-driven rendering already supports.

## Design

### 1. Rename the dimension to `engagement`

Rename the dimension key from `support_engagement` to `engagement` everywhere PQF treats dimension identity as data:

- `config/dimensions.yaml`,
- scorer directory and imports,
- engine and UI tests or fixtures that reference the old key,
- any example or developer documentation that explicitly names the dimension.

The new dimension label should be `Engagement`, with description wording that covers both maintainer responsiveness and audience attention.

Rationale:

- the renamed key matches the expanded scope,
- keeping the old key while broadening the semantics would make the contract misleading,
- the UI already renders dimensions dynamically from `dimensions_meta`, so the rename is primarily a data-contract change rather than a UI architecture change.

### 2. Keep medal gating anchored to support responsiveness

The new `engagement` dimension keeps the existing medal-driving metrics and thresholds:

- `avg_triage_days`,
- `avg_pr_review_days`,
- `response_coverage_rate`,
- `ownership_signal`.

`has_jira_sync` remains informational as it is today.

`repo_views_14d` is also informational-only and must not appear in:

- `required_metrics_for_scoring`,
- bronze criteria,
- silver criteria,
- gold criteria.

This preserves PQF's calibration philosophy:

- maintainer responsiveness remains a high-confidence operational quality signal,
- traffic is visible as portfolio context rather than as a medal determinant,
- a low-traffic but well-operated repository is not penalized,
- missing traffic data does not force `insufficient_data`.

### 3. Add `repo_views_14d` from GitHub traffic

The scorer should call:

- `GET /repos/{owner}/{repo}/traffic/views`

and store the top-level `count` field as:

- `repo_views_14d`

Contract details:

- type: numeric,
- label: `Repo views (14d)`,
- description: `Total GitHub repository page views over the last 14 days.`,
- range: `≥ 0 views`,
- informational: `true`.

The first version intentionally uses only total views:

- no uniques,
- no daily breakdown in the scorer contract,
- no 30-day rollup approximation.

This keeps the metric simple and aligned with the user's current need.

### 4. Traffic error handling and measurability semantics

Traffic availability should be handled independently from support-response measurability.

Behavior:

- if the repo is missing, return the existing no-repo defaults and `repo_views_14d` as `null`,
- if the traffic endpoint succeeds, persist `count` as an integer,
- if the traffic endpoint returns 403, 404, or another non-success response, set `repo_views_14d` to `null`,
- if issue/PR metrics are measurable but traffic is unavailable, the dimension should still score normally.

Important rule:

- `repo_views_14d` must not be added to `required_metrics_for_scoring`.

That keeps the distinction clear:

- support-response metrics determine whether the dimension is scoreable,
- repository traffic is optional context.

### 5. Preserve drift continuity across the rename

Even though the dimension key changes, the medal-driving semantics remain effectively the same. PQF should preserve existing drift clocks rather than resetting them.

Design choice:

- implement a one-time legacy-key migration path from `support_engagement` to `engagement` when loading or normalizing drift history,
- after migration, new writes should only use `engagement`.

Why preserve continuity:

- the rename is conceptual, not a policy reset,
- teams should not lose active remediation windows because of a naming change,
- the current drift tracker keys history directly by dimension name, so continuity needs an explicit bridge.

### 6. UI and portfolio impact

No bespoke UI feature work is required for this design to be useful.

Existing behavior already supports it:

- `engine/assemble.py` carries `informational` output metadata into `dimensions_meta`,
- metric listings already show informational badges,
- metric detail pages already suppress medal-threshold framing for informational metrics.

Expected UI impact after the data contract updates:

- the Dimensions and Product pages show `Engagement` instead of `Support engagement`,
- `repo_views_14d` appears as an informational metric,
- metric distribution pages can render the new metric without scoring implications.

## Validation

The design is correct when:

- the dimension key is `engagement` across assembled portfolio data,
- products retain the same engagement medals they would have received before the rename when traffic data is ignored,
- `repo_views_14d` appears in output metadata and per-product metrics,
- missing traffic data leaves scoring unchanged,
- existing drift windows continue under the new dimension key rather than restarting.

## Testing

Minimum validation:

- scorer unit test for successful traffic view fetch returning `repo_views_14d`,
- scorer unit test for unavailable traffic returning `repo_views_14d = null`,
- scorer unit test proving insufficient support-response samples still behave as before,
- targeted engine or assembly test proving informational metrics do not enter `required_metrics_for_scoring`,
- targeted drift-history test proving legacy `support_engagement` state is preserved under `engagement`,
- UI tests or fixtures updated for the renamed dimension key and informational metric display where the old key was hard-coded.
