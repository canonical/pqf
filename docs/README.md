# PQF Documentation

**[Live dashboard →](https://canonical.github.io/pqf/)**

---

## Using the dashboard

| Page | Description |
|------|-------------|
| [Products Overview](views/overview.md) | The main view — heatmap and products table |
| [Product Detail](views/product-detail.md) | Per-product dimension results and evidence |
| [Dimension Detail](views/dimension-detail.md) | Metrics, rubric, and all-product results for one dimension |

## Vocabulary

| Term | Meaning |
|------|---------|
| **Current** | The product's present result in a table or dimension card |
| **Target** | The result a team is aiming for |
| **Result** | Any scored outcome shown in the UI, including gold / silver / bronze / below minimum / no data / not applicable |
| **Medal** | The scored tiers when a result is awarded or compared to a target |
| **Evidence** | Raw metric values used to explain a result |
| **Framework version** | A full, immutable snapshot of the scoring contract (`framework/versions/<version>/`) |
| **Scoring contract** | One framework version's declared outputs, implementation IDs, required metrics, medal criteria, applicability, and aggregation rules |
| **Measurement** | Raw evidence produced by a scorer runner before a scoring contract filters outputs and applies its criteria |
| **Product set** | The products, component boundaries, composition edges, and targets resolved for one framework version |
| **Active** | The framework version that defines today's official compliance view (scored nightly) |
| **Upcoming** | The next framework version, previewed early (scored weekly and on demand) |
| **Archived** | A retired framework version — its measurements are frozen and never rescored |

Each version's generated product-set artifact is named `portfolio.json`; the filename is retained
for compatibility and is not the preferred term for the product set itself. See
[How versioned scoring works](architecture.md#how-versioned-scoring-works) for the canonical
versioned-scoring explanation.

## Contributing

| Guide | Description |
|-------|-------------|
| [Architecture](architecture.md) | Canonical versioned-scoring explanation, data flow, GHA pipeline, and design decisions |
| [Adding a product](adding-a-product.md) | How to onboard a new product into PQF |
| [Adding a metric](adding-a-metric.md) | How to add a metric to an existing dimension |
| [Adding a dimension/scorer](adding-a-dimension.md) | How to create a new quality dimension and scorer |
| [Run PQF locally](local-scoring.md) | Preview metric, criteria, and product changes in the dashboard |
| [Metric calibration roadmap](metric-calibration-roadmap.md) | Philosophy and remaining phases for scorer/rubric calibration work |

---

> For AI agent contributors, see [AGENTS.md](../AGENTS.md) at the repo root.
