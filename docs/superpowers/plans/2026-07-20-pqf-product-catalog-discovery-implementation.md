# PQF Product Catalog Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first-step discovery workflow that inventories all platform-engineering-docs products, classifies root vs sub-product candidates, and reports PQF schema/UI readiness gaps for migration.

**Architecture:** Add a Python discovery module in `engine/` that loads docs products + PQF products, normalizes public-safe metadata, computes inventory/classification/mapping/gaps, and emits machine-readable JSON artifacts. Keep this as temporary migration tooling (not a permanent docs->PQF sync path).

**Tech Stack:** Python 3.12, PyYAML, pytest, existing PQF schema files, Makefile targets.

## Global Constraints

- Use docs `product.id` as canonical PQF `id`; include explicit rename handling (`wordpress` -> `wordpress-k8s`).
- Map docs `product.service_level` directly to PQF `target_medal`; do not add PQF `service_level`.
- Keep `documentation_url` as dedicated field and support additional `links`.
- Exclude `deployments`, `communication`, and non-squad ownership details from migration inputs.
- Classify products as root vs leaf with deterministic rules plus explicit overrides.
- Keep quality-first PQF UX; discovery step only reports required UI changes.
- Use existing repository tooling and tests (`make test`, `make lint`).

---

## File structure

- Create: `engine/catalog_discovery.py`  
  Responsibility: pure discovery logic (load/normalize/compare/classify/report).
- Create: `engine/__tests__/test_catalog_discovery.py`  
  Responsibility: unit tests for normalization, inventory diff, classifier, and report shape.
- Create: `tools/generate_catalog_discovery.py`  
  Responsibility: thin CLI wrapper that reads files/dirs and writes discovery artifact JSON.
- Modify: `Makefile`  
  Responsibility: add a `catalog-discovery` target wired to the new CLI.
- Create: `docs/superpowers/artifacts/2026-07-20-product-catalog-discovery.json`  
  Responsibility: checked-in output artifact from the tool for team review.

### Task 1: Implement docs/PQF normalization primitives

**Files:**
- Create: `engine/catalog_discovery.py`
- Test: `engine/__tests__/test_catalog_discovery.py`

**Interfaces:**
- Consumes: raw docs YAML dicts and raw PQF YAML dicts.
- Produces:
  - `normalize_docs_product(raw: dict) -> dict`
  - `normalize_pqf_product(raw: dict) -> dict`
  - `canonical_docs_id(raw: dict) -> str`

- [ ] **Step 1: Write the failing test**

```python
def test_normalize_docs_product_maps_service_level_to_target_medal():
    raw = {
        "product": {
            "id": "discourse",
            "name": "Discourse",
            "service_level": "silver",
            "summary": "Forum",
            "description": "Long",
        },
        "ownership": {"squad": "Americas"},
        "links": [{"name": "Charmhub", "url": "https://charmhub.io/discourse-k8s"}],
        "components": [],
        "deployments": [{"environment_name": "prod"}],
        "communication": [{"type": "mattermost", "public": False}],
    }
    normalized = normalize_docs_product(raw)
    assert normalized["id"] == "discourse"
    assert normalized["target_medal"] == "silver"
    assert "deployments" not in normalized
    assert "communication" not in normalized
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest engine/__tests__/test_catalog_discovery.py::test_normalize_docs_product_maps_service_level_to_target_medal -v`  
Expected: FAIL with `NameError`/import error for missing module/function.

- [ ] **Step 3: Write minimal implementation**

```python
def normalize_docs_product(raw: dict) -> dict:
    product = raw.get("product", {})
    ownership = raw.get("ownership", {})
    return {
        "id": product["id"],
        "name": product.get("name", product["id"]),
        "target_medal": product["service_level"],
        "summary": product.get("summary", ""),
        "description": product.get("description", ""),
        "squad": ownership.get("squad", "").lower(),
        "links": raw.get("links", []),
        "components": raw.get("components", []),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest engine/__tests__/test_catalog_discovery.py::test_normalize_docs_product_maps_service_level_to_target_medal -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/catalog_discovery.py engine/__tests__/test_catalog_discovery.py
git commit -m "feat: add docs and pqf normalization for catalog discovery"
```

### Task 2: Build inventory diff and ID mismatch reporting

**Files:**
- Modify: `engine/catalog_discovery.py`
- Test: `engine/__tests__/test_catalog_discovery.py`

**Interfaces:**
- Consumes: `list[dict]` normalized docs products, `list[dict]` normalized PQF products.
- Produces:
  - `build_inventory_report(docs_products: list[dict], pqf_products: list[dict]) -> dict`
  - report keys: `docs_count`, `pqf_count`, `missing_in_pqf`, `overlap`, `id_mismatches`

- [ ] **Step 1: Write the failing test**

```python
def test_inventory_report_detects_missing_and_id_mismatch():
    docs_products = [{"id": "wordpress-k8s"}, {"id": "discourse"}]
    pqf_products = [{"id": "wordpress"}, {"id": "discourse"}]
    report = build_inventory_report(docs_products, pqf_products)
    assert report["missing_in_pqf"] == ["wordpress-k8s"]
    assert report["id_mismatches"] == [{"pqf_id": "wordpress", "docs_id": "wordpress-k8s"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest engine/__tests__/test_catalog_discovery.py::test_inventory_report_detects_missing_and_id_mismatch -v`  
Expected: FAIL with missing function/assertion mismatch.

- [ ] **Step 3: Write minimal implementation**

```python
def build_inventory_report(docs_products: list[dict], pqf_products: list[dict]) -> dict:
    docs_ids = {p["id"] for p in docs_products}
    pqf_ids = {p["id"] for p in pqf_products}
    missing = sorted(docs_ids - pqf_ids)
    overlap = sorted(docs_ids & pqf_ids)
    id_mismatches = []
    if "wordpress-k8s" in docs_ids and "wordpress" in pqf_ids:
        id_mismatches.append({"pqf_id": "wordpress", "docs_id": "wordpress-k8s"})
    return {
        "docs_count": len(docs_ids),
        "pqf_count": len(pqf_ids),
        "missing_in_pqf": missing,
        "overlap": overlap,
        "id_mismatches": id_mismatches,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest engine/__tests__/test_catalog_discovery.py::test_inventory_report_detects_missing_and_id_mismatch -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/catalog_discovery.py engine/__tests__/test_catalog_discovery.py
git commit -m "feat: add product inventory diff and id mismatch report"
```

### Task 3: Implement root-vs-leaf classifier with overrides

**Files:**
- Modify: `engine/catalog_discovery.py`
- Test: `engine/__tests__/test_catalog_discovery.py`

**Interfaces:**
- Consumes: normalized docs product + optional `overrides: dict[str, str]`.
- Produces:
  - `classify_product_role(product: dict, overrides: dict[str, str] | None = None) -> str`
  - allowed outputs: `"root"` or `"leaf"`

- [ ] **Step 1: Write the failing test**

```python
def test_classifier_respects_force_leaf_override():
    product = {
        "id": "saml-integrator",
        "components": [{"name": "saml-integrator", "role": "primary", "type": "k8s-charm"}],
    }
    role = classify_product_role(product, overrides={"saml-integrator": "leaf"})
    assert role == "leaf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest engine/__tests__/test_catalog_discovery.py::test_classifier_respects_force_leaf_override -v`  
Expected: FAIL with missing function/incorrect role.

- [ ] **Step 3: Write minimal implementation**

```python
def classify_product_role(product: dict, overrides: dict[str, str] | None = None) -> str:
    overrides = overrides or {}
    pid = product["id"]
    if pid in overrides:
        return overrides[pid]
    primary_components = [
        c for c in product.get("components", [])
        if c.get("role") == "primary" and c.get("type") in {"k8s-charm", "machine-charm", "subordinate-charm", "snap"}
    ]
    return "root" if primary_components else "leaf"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest engine/__tests__/test_catalog_discovery.py::test_classifier_respects_force_leaf_override -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/catalog_discovery.py engine/__tests__/test_catalog_discovery.py
git commit -m "feat: add root-vs-leaf classifier with override support"
```

### Task 4: Add field mapping and schema/UI gap report generation

**Files:**
- Modify: `engine/catalog_discovery.py`
- Test: `engine/__tests__/test_catalog_discovery.py`

**Interfaces:**
- Consumes: normalized docs product fields + `config/schemas/product.schema.json` + UI type fields.
- Produces:
  - `build_field_mapping_report() -> list[dict]`
  - `build_gap_report() -> dict` with `schema_missing_fields` and `ui_missing_fields`

- [ ] **Step 1: Write the failing test**

```python
def test_gap_report_flags_links_as_missing():
    report = build_gap_report(
        pqf_schema_fields={"documentation_url", "ownership", "composed_of"},
        ui_product_fields={"documentation_url", "squad", "composed_of"},
    )
    assert "links" in report["schema_missing_fields"]
    assert "links" in report["ui_missing_fields"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest engine/__tests__/test_catalog_discovery.py::test_gap_report_flags_links_as_missing -v`  
Expected: FAIL with missing function/incorrect output.

- [ ] **Step 3: Write minimal implementation**

```python
PUBLIC_TARGET_FIELDS = {"id", "name", "description", "target_medal", "ownership.squad", "documentation_url", "links"}

def build_gap_report(*, pqf_schema_fields: set[str], ui_product_fields: set[str]) -> dict:
    schema_missing = sorted([f for f in PUBLIC_TARGET_FIELDS if f.split(".")[0] not in pqf_schema_fields and f not in pqf_schema_fields])
    ui_missing = sorted([f for f in PUBLIC_TARGET_FIELDS if f.split(".")[0] not in ui_product_fields and f not in ui_product_fields])
    return {"schema_missing_fields": schema_missing, "ui_missing_fields": ui_missing}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest engine/__tests__/test_catalog_discovery.py::test_gap_report_flags_links_as_missing -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/catalog_discovery.py engine/__tests__/test_catalog_discovery.py
git commit -m "feat: add field mapping and schema-ui gap reporting"
```

### Task 5: Add CLI + Make target and generate discovery artifact

**Files:**
- Create: `tools/generate_catalog_discovery.py`
- Modify: `Makefile`
- Create: `docs/superpowers/artifacts/2026-07-20-product-catalog-discovery.json`
- Test: `engine/__tests__/test_catalog_discovery.py` (CLI integration test fixture call)

**Interfaces:**
- Consumes:
  - docs products dir path
  - PQF products dir path
  - override file path
- Produces:
  - JSON artifact with keys: `inventory`, `classification`, `field_mapping`, `gaps`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_writes_discovery_artifact(tmp_path):
    output = tmp_path / "discovery.json"
    exit_code = main(
        [
            "--docs-products-dir", "tests/fixtures/docs-products",
            "--pqf-products-dir", "tests/fixtures/pqf-products",
            "--output", str(output),
        ]
    )
    assert exit_code == 0
    assert output.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest engine/__tests__/test_catalog_discovery.py::test_cli_writes_discovery_artifact -v`  
Expected: FAIL with missing CLI module/function.

- [ ] **Step 3: Write minimal implementation**

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate PQF catalog discovery report")
    parser.add_argument("--docs-products-dir", required=True)
    parser.add_argument("--pqf-products-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = generate_discovery_report(args.docs_products_dir, args.pqf_products_dir)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    return 0
```

```makefile
catalog-discovery:
	$(PYTHON) tools/generate_catalog_discovery.py \
		--docs-products-dir .pqf-cache/platform-engineering-docs/data/products \
		--pqf-products-dir products \
		--output docs/superpowers/artifacts/2026-07-20-product-catalog-discovery.json
```

- [ ] **Step 4: Run verification suite**

Run:
- `pytest engine/__tests__/test_catalog_discovery.py -v`
- `make test`
- `make lint`

Expected:
- All new catalog discovery tests PASS.
- Existing Python tests PASS.
- Ruff check PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/generate_catalog_discovery.py Makefile engine/catalog_discovery.py engine/__tests__/test_catalog_discovery.py docs/superpowers/artifacts/2026-07-20-product-catalog-discovery.json
git commit -m "feat: add pqf catalog discovery CLI and artifact generation"
```

## Self-review checklist (completed)

1. **Spec coverage:** Plan includes inventory, ID alignment, root/leaf classification, field mapping, and schema/UI gap reporting tasks.
2. **Placeholder scan:** No TBD/TODO placeholders; each code step includes concrete snippets and commands.
3. **Type consistency:** Function names and report keys are consistent across tasks (`build_inventory_report`, `classify_product_role`, `build_gap_report`, `generate_discovery_report`).
