# PQF Documentation

**[Live dashboard →](https://srbouffard.github.io/pqf/)**

---

## Using the dashboard

| Page | Description |
|------|-------------|
| [Portfolio Overview](views/overview.md) | The main view — heatmap and products table |
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

## Contributing

| Guide | Description |
|-------|-------------|
| [Architecture](architecture.md) | How the system works — data flow, GHA pipeline, design decisions |
| [Adding a product](adding-a-product.md) | How to onboard a new product into PQF |
| [Adding a dimension/scorer](adding-a-dimension.md) | How to create a new quality dimension and scorer |
| [Running scorers locally](local-scoring.md) | Score products locally and preview changes in the dashboard |
| [Metric calibration roadmap](metric-calibration-roadmap.md) | Philosophy and remaining phases for scorer/rubric calibration work |

---

> For AI agent contributors, see [AGENTS.md](../AGENTS.md) at the repo root.
