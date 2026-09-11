# Adding a Product

This guide explains how to onboard a new product into PQF.

---

## When to add a product

Add a product when a Canonical Platform Engineering team wants to start tracking quality compliance for a product that:
- Has at least one charm or snap repository on GitHub under the `canonical/` organisation
- Has an owning squad (AMER, EMEA, or APAC)
- Has a target result grade the team is committing to, for the framework version it joins in

---

## Step 0: Pick the framework version it joins in

Catalog membership is **version-scoped**. Every product, component, and composition edge declares
the framework version it enters in, so adding a product never silently changes an older version's
results.

Read `framework/versions/*/framework.yaml` to see the current lifecycle state. Today **V0 is
active** and **V1 is upcoming**.

- Onboard into the **active** version (`introduced_in: v0`) when the product should count towards
  today's official compliance view immediately.
- Onboard into the **upcoming** version (`introduced_in: v1`) when the product should only appear
  in the planning/readiness view until that version activates.
- You cannot introduce a product in an **archived** version. Archived results are frozen and are
  never recomputed.

---

## Step 1: Create the product YAML file

Create `products/<product-id>.yaml`. Use lowercase hyphenated IDs (e.g., `discourse`, `matrix`, `wordpress-k8s`).

Every product YAML has a root node (`product_type: root`) that owns one or more leaf products (`product_type: charm` or `snap`) declared in `composed_of`.

### Example 1: Single-charm product

```yaml
id: netbox
product_type: root
name: "NetBox"
description: "IP address management and network infrastructure management tool."
lifecycle: stable
introduced_in: v0
targets:
  v0: bronze
  v1: bronze
ownership:
  squad: emea
documentation_url: "https://netboxlabs.com/"
composed_of:
  - id: netbox-k8s
    product_type: charm
    introduced_in: v0
    source:
      repo: canonical/netbox-k8s-operator
    allure_report_url: "https://canonical.github.io/netbox-k8s-operator/_latest"
```

### Example 2: Multi-charm product with context refs

```yaml
id: wazuh
product_type: root
name: "Wazuh"
description: "Open-source security platform for threat detection and response."
lifecycle: stable
introduced_in: v0
targets:
  v0: silver
ownership:
  squad: emea
documentation_url: "https://wazuh.com/"
composed_of:
  - id: wazuh-server
    product_type: charm
    introduced_in: v0
    source:
      repo: canonical/wazuh-server-operator
    allure_report_url: "https://canonical.github.io/wazuh-server-operator/_latest"
  - id: wazuh-indexer
    product_type: charm
    introduced_in: v1
    source:
      repo: canonical/wazuh-indexer-operator
context_refs:
  - label: "Traefik K8s"
    repo: canonical/traefik-k8s-operator
```

Here `wazuh-indexer` is absent from V0 entirely — including search, aggregate counts, and the
parent's roll-up — and appears only in the V1 readiness view.

---

## Version membership and targets

### `introduced_in` / `retired_in`

`introduced_in` is required on every product, inline component, standalone component reference, and
composition edge. `retired_in` is optional. Inclusion is start-inclusive and retirement-exclusive:

```text
introduced_in <= selected version < retired_in
```

A composition edge carries its own boundaries, which is how an existing standalone component can
join or leave a root product at a later framework version:

```yaml
composed_of:
  - ref: saml-integrator
    introduced_in: v1        # this component joins this root in V1, not V0
```

`make validate` rejects:

- boundaries referencing unknown framework versions,
- retirement at or before introduction,
- a composition edge active when either endpoint is inactive in the selected version,
- references to components that do not exist in the selected version.

### `targets`

Targets are **sparse, version-scoped declarations**. The target for a selected version is the
declaration with the greatest sequence not exceeding that version, so you only declare a version
where the commitment changes:

```yaml
targets:
  v0: bronze     # in force for v0
  v1: silver     # raises the commitment from v1 onwards
```

A product must declare a target at its introduction boundary. Validation fails if a framework
version cannot resolve a target for a product that is active in it.

Inline components inherit their parent root's target unless they own a standalone target under the
existing product graph rules.

### When to use `composed_of` vs `context_refs`

> **Use `composed_of` (inline leaf) when:**
> - Your squad owns the quality of this charm/snap
> - It belongs to exactly this one root product
>
> **Use `composed_of` with `ref:` (standalone leaf) when:**
> - It is a standalone product that also gets tracked independently (it has its own `products/<id>.yaml`)
>
> **Use `context_refs` when:**
> - It is owned by another squad
> - You only want it visible for context, not affecting your result

`context_refs` entries are shown in the UI but are **never** included in result computation.

### Optional root-level fields

```yaml
ownership:
  stakeholders:           # Optional. List of stakeholder team names.
    - "IS"
  users:                  # Optional. List of user groups.
    - "Internal Canonical"
```

### Allure report URL

If a leaf charm publishes an Allure test report to GitHub Pages, set `allure_report_url` on that leaf:

```yaml
allure_report_url: "https://canonical.github.io/{repo-name}/_latest"
```

The `_latest` path is a symlink maintained by the charm's CI — it always points to the most recent report. To verify it exists:

```bash
curl -I https://canonical.github.io/<repo-name>/_latest/widgets/summary.json
# Expected: HTTP/2 200
```

If the charm doesn't publish Allure reports yet, omit the field or set it to `""`. The `test_verification` scorer will return unrated for coverage/stability but won't error.

---

## Step 2: Validate and open a pull request

```bash
make validate
```

Commit your new `products/<id>.yaml` and open a PR. CI validates the YAML against the schema, runs
the version-boundary and target-resolution checks for every framework version, publishes a semantic
change report classifying your change (here: catalog membership/target), and runs the test suite.
A reviewer will check that:
- The `source.repo` slugs are correct
- The `squad` matches the team's actual ownership
- `introduced_in` names the intended framework version
- The declared `targets` are realistic for each version they apply to

---

## Step 3: After merging

Once merged, `compute-metrics.yml` recomputes every **live** framework version affected by the
catalog change and will:
1. Run the selected framework's dimensions against the new product's leaf units
2. Write `computed/versions/<version>/<id>.json` (a `leaf_metrics` envelope keyed by leaf product ID)
3. Regenerate `public/versions/<version>/portfolio.json` (including the new product)
4. Regenerate `public/framework-versions.json`
5. Deploy the updated dashboard

The product appears in the active view within 24 hours of merge (or immediately if you trigger the
workflow manually via `workflow_dispatch` with the framework version). A product introduced only in
the upcoming version appears after that version's weekly refresh, and only under that version in
the UI's framework selector.

---

## Local scoring (optional)

Follow [Run PQF locally](local-scoring.md) with the new product ID and an explicit
`FRAMEWORK_VERSION`. The default workflow uses GitHub authentication from `gh` and does not require
an AI API key.
