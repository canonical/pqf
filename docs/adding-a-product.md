# Adding a Product

This guide explains how to onboard a new product into PQF.

---

## When to add a product

Add a product when a Canonical Platform Engineering team wants to start tracking quality compliance for a product that:
- Has at least one charm or snap repository on GitHub under the `canonical/` organisation
- Has an owning squad (AMER, EMEA, or APAC)
- Has a target medal grade the team is committing to

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
target_medal: bronze
ownership:
  squad: emea
documentation_url: "https://netboxlabs.com/"
composed_of:
  - id: netbox-k8s
    product_type: charm
    source:
      repo: canonical/netbox-k8s-operator
    target_medal: bronze
    allure_report_url: "https://canonical.github.io/netbox-k8s-operator/_latest"
```

### Example 2: Multi-charm product with context refs

```yaml
id: wazuh
product_type: root
name: "Wazuh"
description: "Open-source security platform for threat detection and response."
lifecycle: stable
target_medal: silver
ownership:
  squad: emea
documentation_url: "https://wazuh.com/"
composed_of:
  - id: wazuh-server
    product_type: charm
    source:
      repo: canonical/wazuh-server-operator
    target_medal: silver
    allure_report_url: "https://canonical.github.io/wazuh-server-operator/_latest"
  - id: wazuh-indexer
    product_type: charm
    source:
      repo: canonical/wazuh-indexer-operator
    target_medal: silver
context_refs:
  - label: "Traefik K8s"
    repo: canonical/traefik-k8s-operator
```

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
> - You only want it visible for context, not affecting your medal

`context_refs` entries are shown in the UI but are **never** included in medal computation.

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

## Step 2: Open a pull request

Commit your new `products/<id>.yaml` and open a PR. CI will lint the YAML and run the test suite. A reviewer will check that:
- The `source.repo` slugs are correct
- The `squad` matches the team's actual ownership
- The `target_medal` is realistic

---

## Step 3: After merging

Once merged, the nightly `compute-metrics` workflow will:
1. Run all scorers against the new product's leaf units
2. Write `computed/<id>.json` (a `leaf_metrics` envelope keyed by leaf product ID)
3. Regenerate `public/portfolio.json` (including the new product)
4. Deploy the updated dashboard

The product will appear on the dashboard within 24 hours of merge (or immediately if you trigger the workflow manually via `workflow_dispatch`).

---

## Local scoring (optional)

To score the product locally before opening a PR:

```bash
export GITHUB_TOKEN=<your-pat>
export OPENROUTER_API_KEY=<your-key>
make score PRODUCT=<id>
```

Results are written to `.pqf-score/<id>/` (gitignored).
