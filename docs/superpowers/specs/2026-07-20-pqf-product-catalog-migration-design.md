# PQF product catalog migration design

Date: 2026-07-20  
Status: Approved for planning

## 1. Context and goals

PQF is ready to scale from a small portfolio set to the full Platform Engineering catalog currently stored in `canonical/platform-engineering-docs:data/products/*.yaml`.

This design defines the first step and migration direction to:

1. Identify all products to bring into PQF.
2. Determine root products vs sub-products.
3. Align fields that should become public PQF product metadata.
4. Keep private/internal operational data out of PQF.

## 2. Current state summary

- `platform-engineering-docs` product definitions found: **34**
- Current PQF root product definitions: **8**
- Products missing in PQF: **27**
- Existing overlap: discourse, indico, jenkins, matrix, mattermost, netbox, wazuh
- ID mismatch found: PQF `wordpress` vs docs `wordpress-k8s`

Docs product schema currently centers on:
- `product` (id/name/summary/description/service_level)
- `ownership`
- `communication`
- `links`
- `components`
- `deployments`

PQF currently centers on:
- quality graph (`root`, `charm`, `snap`, `composed_of`, `context_refs`)
- quality metadata (`target_medal`, dimensions, drift)
- lightweight product metadata (`name`, `description`, `lifecycle`, `ownership.squad`, `documentation_url`)

## 3. Source-of-truth and transition model

### End state

- PQF becomes the source of truth for **public product metadata + quality posture**.
- Internal docs consume PQF-aligned catalog data (implementation outside this task).

### Transition

- Use temporary migration tooling for copy/reconciliation during cutover.
- Isolate the temporary docs fetch/import step outside the engine (Makefile
  targets `catalog-discovery-fetch` / `catalog-import-products` +
  `tools/fetch_platform_engineering_docs_products.py` +
  `tools/import_platform_engineering_docs_products.py`) so it can be removed
  cleanly after cutover.
- Do **not** keep a permanent docs->PQF import pipeline.
- Optional temporary drift-check between repos is acceptable until cutover is complete.

## 4. Data mapping decisions

### 4.1 Include in PQF

- `product.id` -> `id` (PQF IDs aligned to docs IDs)
- `product.name` -> `name`
- `product.description` / `product.summary` -> PQF display text (with optional short-summary support)
- `product.service_level` -> `target_medal` (no separate `service_level` field in PQF)
- `ownership.squad` -> `ownership.squad`
- dedicated product docs link -> `documentation_url`
- additional public links -> new `links` collection (`name`, `summary?`, `url`)
- component relationships -> PQF `composed_of` and `context_refs` via role mapping

### 4.2 Exclude from PQF (this phase)

- `deployments` (contains non-public operational details)
- `communication` (expected to be mostly private channels for now)
- non-squad ownership details (stakeholders/users)

## 5. Product classification model (root vs sub-product)

Not every docs product should become a top-level PQF root entry.

Classifier approach:

1. Parse each docs product YAML.
2. Build a component graph from `components`.
3. Detect scorable candidate leaves (charms/snaps with canonical repos).
4. Classify as:
   - **Root** when portfolio-facing as a product.
   - **Leaf/sub-product** when primarily reusable/embedded in other products.
5. Support explicit overrides (`force_root`, `force_leaf`) for ambiguous cases.
6. Generate:
   - `composed_of` for team-owned/scored components.
   - `context_refs` for dependency/context-only components.

## 6. PQF schema and UI implications

### Schema

- Keep existing quality graph model.
- Add support for `links`.
- Keep `documentation_url` as a dedicated first-class field.
- Keep only `ownership.squad` for this phase.
- Preserve existing strict exclusion of private/internal structures.

### UI

- Keep quality-first UX (medals/drift/dimensions remain primary).
- Keep prominent Docs button (from `documentation_url`).
- Add a Related links section for additional public links.
- No rendering of deployments/private communication data.

## 7. First-step deliverables

The immediate discovery deliverable consists of:

1. Product inventory:
   - all docs products
   - missing PQF products
   - ID conflicts
2. Proposed root vs sub-product classification table.
3. Field mapping matrix:
   - docs field
   - PQF destination
   - include/exclude decision
   - rationale
4. Gap analysis of required PQF schema/UI changes to support migration.

## 8. Risks and mitigations

- **Misclassification risk** (root vs leaf): mitigate with explicit override list and review pass.
- **ID churn impact** (e.g., `wordpress` -> `wordpress-k8s`): mitigate with migration map and link compatibility checks.
- **Scope creep into private metadata**: enforce hard exclusions (`deployments`, non-public communication).

## 9. Out of scope

- Implementation of internal docs repo changes consuming PQF as source.
- Permanent cross-repo synchronization service.
- Migration of private/internal operational data into PQF.
