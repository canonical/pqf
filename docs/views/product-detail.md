# Product Detail

The Product Detail page shows the full quality breakdown for a single product — one row per quality dimension with current result, target, and evidence.

![Product Detail](../screenshots/product-detail.png)

---

## Header Card

The header shows:
- **Product name and description**
- **Overall result** — the lowest result achieved across all dimensions (the bottleneck)
- **Target result** — the committed target
- **Squad** — the owning team, linked to their GitHub team page

---

## Dimension Score Cards

Each quality dimension has its own card showing:

| Column | Description |
|--------|-------------|
| **Dimension** | Dimension name, linking to its Dimension Detail page |
| **Current** | Current result for this dimension (may differ from the overall) |
| **Evidence** | The raw metric values used to compute the result |

### Evidence column

Each evidence row shows one metric with its current value. If the metric is compared against a threshold in the target rubric, the display shows `value / threshold` colour-coded:

- **Green** — value meets or exceeds the threshold for the target tier
- **Red** — value falls short of the threshold

For measured boolean metrics, `✓` (true) or `✗` (false) is shown, with accessible text equivalents.
Informational metrics are not threshold-coloured. Measured string values show the detected version;
an empty string means **Not adopted**. String adoption criteria such as `uses_sphinx_stack != ""`
test adoption, not numeric version ordering.

Every metric is a structured outcome: `measured` carries a string, number, or boolean value;
`not_applicable` and `insufficient_data` carry a null value and a required reason. Unavailable
evidence appears neutrally as **N/A** or **Insufficient data**, with a visible, accessible reason,
even when the entire dimension is N/A. Legacy scalar artifacts are rejected at load time rather
than converted or silently displayed.

Root products summarize in-scope component evidence. Missing or insufficient component evidence
remains visible and cannot be hidden by another component's measured success. Expanding a metric
shows each component's outcome and reason; excluded components do not affect the root summary.

---

## Navigation

Click any dimension name in the evidence cards to jump to the [Dimension Detail](dimension-detail.md) page for that dimension, which shows the full metric descriptions and the result rubric.
