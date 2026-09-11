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
| ⬇ Below minimum | `#666` | Measured, but did not meet minimum criteria |
| — No data | `#666` | Scoring data not yet available |

### Framework version selector

Every page is scoped to a framework version. The selector in the top-right switches versions and
preserves the current sub-route — routes are `#/<version>/...`. Options are grouped by lifecycle
state (Upcoming, Active, Archived) from `public/framework-versions.json`, which is the sole
authority for which versions exist and how they are labelled. Upcoming versions also show when the
data was last refreshed, because they are regenerated weekly rather than nightly.

Archived versions stay selectable and keep serving their frozen measurements; they are never
rescored. The pre-versioning snapshot is served separately at `/legacy/` and is not linked from
this UI.

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

There are no remediation deadlines and no drift clocks: the summary is a point-in-time compliance
count for the selected framework version, not a countdown.

---

## Product Heatmap

The **Heatmap** shows each product's result across every quality dimension, making it easy to spot which dimensions need the most attention across tracked products.

Rows are products; columns are quality dimensions. Each cell shows the result for that product × dimension combination using the same colour coding as the Products table.
