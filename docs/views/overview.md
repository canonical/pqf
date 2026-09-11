# Products Overview

The Products Overview is the main landing page of PQF. It shows the quality state of Canonical Platform Engineering's tracked products at a glance.

![Products Overview](../screenshots/overview.png)

---

## Products Table

The **Products** table lists every tracked product with its current quality state.

| Column | Description |
|--------|-------------|
| **Product** | Product name, linking to its detail page |
| **Current** | Current overall result (gold / silver / bronze / below minimum / no data) |
| **Target** | The result the team has committed to achieving |
| **Squad** | Owning team (AMER / EMEA / APAC), linked to the GitHub team |
| **Actions** | Link to the Product Detail page |

### Result colours

| Result | Colour | Meaning |
|-------|--------|---------|
| 🥇 Gold | `#C7962F` | Meets all gold-tier criteria |
| 🥈 Silver | `#8F8F8F` | Meets all silver-tier criteria |
| 🥉 Bronze | `#9E622A` | Meets all bronze-tier criteria |
| ⬇ Below minimum | `#C7162B` | Measured, but did not meet minimum criteria |
| — No data | `#666` | Scoring data not yet available |

### Framework compliance summary

The overview includes the framework compliance summary from the selected portfolio artifact. It
shows aggregate counts for products meeting target, falling below target, or lacking sufficient
data. This summary is rendered directly from the portfolio payload and is not recomputed in the
UI.

| Field | Meaning |
|-------|---------|
| Meeting target | Products at or above their target result |
| Below target | Products measured below target |
| Insufficient data | Products that could not be scored confidently |

---

## Product Heatmap

The **Heatmap** shows each product's result across every quality dimension, making it easy to spot which dimensions need the most attention across tracked products.

Rows are products; columns are quality dimensions. Each cell shows the result for that product × dimension combination using the same colour coding as the Products table.
