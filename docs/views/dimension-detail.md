# Dimension Detail

The Dimension Detail page explains everything about one quality dimension — what metrics are measured, how results are assigned, and where every product currently stands.

![Dimension Detail](../screenshots/dimension-detail.png)

---

## Metrics Card

The **Metrics** card lists every output metric for this dimension.

| Column | Description |
|--------|-------------|
| **Metric** | Human-readable name of the metric |
| **Description** | What it measures and how |
| **Type / Range** | `boolean` (true/false), `number` with the value range, or `string` (for example, a detected version) |
| **Method** | How the metric is computed |

### AI badge

Metrics marked **✦ AI** are scored by an LLM (Claude via OpenRouter) rather than deterministic API checks. These metrics involve qualitative judgements — for example, whether documentation covers all four Diátaxis doc types.

Fully deterministic metrics (GitHub API checks, file existence, etc.) show **Deterministic**.

---

## Result Rubric

The **Result Rubric** shows exactly what a product needs to achieve each result tier.

Each row is one criterion in the format `**Metric label** expression` (e.g., `**Coverage** >= 80`). Hover over any criterion to see the full metric description as a tooltip.

Result tiers are cumulative — to earn gold, a product must also meet all bronze and silver criteria.

---

## Product Scores

The bottom table shows every tracked product's current result for this dimension, sorted by result (best first). Click any product name to jump to its [Product Detail](product-detail.md) page.

## Metric Distribution

Click a metric to compare root and component evidence. Every row retains its structured measured,
N/A, or insufficient-data state and any unavailable-evidence reason. N/A has a separate count and
is excluded from the distribution denominator; neither N/A nor insufficient data is a measured
failure. Informational measurements are counted as **Measured**, not as missing data.

Numeric metrics retain gap-to-target analysis. String metrics use exact equality/inequality
criteria (including `uses_sphinx_stack != ""` for adoption) and have no numeric gap or version
ordering. An empty measured string displays **Not adopted**.
