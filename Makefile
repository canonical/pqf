# PQF — Product Quality Framework
# Usage: make <target>
# All Python targets assume the venv/dev deps are installed: make install
# All UI targets run inside ui/

.DEFAULT_GOAL := help
.PHONY: help install install-ui install-all \
	lint format format-check \
	validate \
	test test-ui test-all \
	build dev \
	audit audit-python audit-ui \
	score score-docs score-no-llm \
	score-all score-all-no-llm _merge _assemble \
	e2e _require-github-token _require-openrouter-key \
	catalog-discovery catalog-discovery-fetch catalog-discovery-report \
	catalog-import-products

PYTHON := python3
PIP    := pip
NPM    := npm
SCORE_DIR := .pqf-score

# Auto-populate GITHUB_TOKEN from `gh auth token` when not already set.
# In CI (GitHub Actions) the token is injected directly; locally this means
# you just need `gh` installed and authenticated — no export needed.
GITHUB_TOKEN ?= $(shell gh auth token 2>/dev/null)
export GITHUB_TOKEN

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  PQF — Product Quality Framework"
	@echo ""
	@echo "  Setup"
	@echo "    make install        Install Python dev dependencies"
	@echo "    make install-ui     Install Node/UI dependencies"
	@echo "    make install-all    Install everything"
	@echo ""
	@echo "  Python"
	@echo "    make lint           Lint Python with ruff"
	@echo "    make format         Auto-format Python with ruff"
	@echo "    make format-check   Check Python formatting without modifying"
	@echo "    make validate       Validate config YAML files against JSON Schemas"
	@echo "    make test           Run Python unit tests"
	@echo ""
	@echo "  UI (React/TypeScript)"
	@echo "    make test-ui        Run Vitest unit tests"
	@echo "    make build          Build the React app (ui/dist/)"
	@echo "    make dev            Start Vite dev server"
	@echo "    make e2e            Run Playwright end-to-end tests"
	@echo ""
	@echo "  Combined"
	@echo "    make test-all       Run both Python and UI tests"
	@echo ""
	@echo "  Security"
	@echo "    make audit          Run pip-audit + npm audit"
	@echo "    make audit-python   Run pip-audit only"
	@echo "    make audit-ui       Run npm audit only"
	@echo ""
	@echo "  Scoring (requires GITHUB_TOKEN; OPENROUTER_API_KEY optional)"
	@echo "    make score PRODUCT=<id>              Score one product (all dimensions, with LLM)"
	@echo "    make score-no-llm PRODUCT=<id>       Score one product (skip AI doc checks)"
	@echo "    make score-docs PRODUCT=<id>         Run only the documentation scorer"
	@echo "    make score-all                       Score all products + rebuild portfolio.json (with LLM)"
	@echo "    make score-all-no-llm                Score all products + rebuild portfolio.json (no LLM)"
	@echo "    make catalog-discovery               Generate docs-vs-PQF catalog discovery artifact"
	@echo "    make catalog-import-products         Import all docs products into products/ (temporary migration)"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
install:
	$(PIP) install -e ".[dev]"

install-ui:
	cd ui && $(NPM) install

install-all: install install-ui

# ── Config validation ─────────────────────────────────────────────────────────
validate:
	$(PYTHON) -m engine.validate

# ── Python: lint & format ────────────────────────────────────────────────────
lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .

# ── Python: tests ─────────────────────────────────────────────────────────────
test:
	pytest --tb=short

# ── UI: tests, build, dev ─────────────────────────────────────────────────────
test-ui:
	cd ui && $(NPM) test

build:
	cd ui && $(NPM) run build

dev:
	cd ui && $(NPM) run dev

e2e:
	cd ui && $(NPM) run e2e

# ── Combined ──────────────────────────────────────────────────────────────────
test-all: test test-ui

# ── Security audits ───────────────────────────────────────────────────────────
audit-python:
	pip-audit

audit-ui:
	cd ui && $(NPM) audit --audit-level=high

audit: audit-python audit-ui

# ── Scoring ───────────────────────────────────────────────────────────────────
# Usage: make score PRODUCT=matrix
PRODUCT ?= $(error PRODUCT is required. Usage: make score PRODUCT=matrix)

score: _require-github-token _require-openrouter-key
	@echo "Scoring product: $(PRODUCT)"
	@mkdir -p $(SCORE_DIR)/$(PRODUCT)
	$(PYTHON) scorers/test_verification/scorer.py --product-yaml products/$(PRODUCT).yaml \
		> $(SCORE_DIR)/$(PRODUCT)/test_verification.json
	$(PYTHON) scorers/documentation/scorer.py --product-yaml products/$(PRODUCT).yaml \
		> $(SCORE_DIR)/$(PRODUCT)/documentation.json
	$(PYTHON) scorers/substrate_compat/scorer.py --product-yaml products/$(PRODUCT).yaml \
		> $(SCORE_DIR)/$(PRODUCT)/substrate_compat.json
	$(PYTHON) scorers/security_ssdlc/scorer.py --product-yaml products/$(PRODUCT).yaml \
		> $(SCORE_DIR)/$(PRODUCT)/security_ssdlc.json
	$(PYTHON) scorers/support_engagement/scorer.py --product-yaml products/$(PRODUCT).yaml \
		> $(SCORE_DIR)/$(PRODUCT)/support_engagement.json
	@echo ""
	@echo "Results in $(SCORE_DIR)/$(PRODUCT)/"
	@for f in $(SCORE_DIR)/$(PRODUCT)/*.json; do echo "  $$f:"; cat $$f | $(PYTHON) -m json.tool --indent 2; echo ""; done

score-no-llm: _require-github-token
	@echo "Scoring product: $(PRODUCT) (LLM checks skipped — diataxis/style will be 0/false)"
	@mkdir -p $(SCORE_DIR)/$(PRODUCT)
	$(PYTHON) scorers/test_verification/scorer.py --product-yaml products/$(PRODUCT).yaml \
		> $(SCORE_DIR)/$(PRODUCT)/test_verification.json
	OPENROUTER_API_KEY= $(PYTHON) scorers/documentation/scorer.py --product-yaml products/$(PRODUCT).yaml \
		> $(SCORE_DIR)/$(PRODUCT)/documentation.json
	$(PYTHON) scorers/substrate_compat/scorer.py --product-yaml products/$(PRODUCT).yaml \
		> $(SCORE_DIR)/$(PRODUCT)/substrate_compat.json
	$(PYTHON) scorers/security_ssdlc/scorer.py --product-yaml products/$(PRODUCT).yaml \
		> $(SCORE_DIR)/$(PRODUCT)/security_ssdlc.json
	$(PYTHON) scorers/support_engagement/scorer.py --product-yaml products/$(PRODUCT).yaml \
		> $(SCORE_DIR)/$(PRODUCT)/support_engagement.json
	@echo ""
	@echo "Results in $(SCORE_DIR)/$(PRODUCT)/"
	@for f in $(SCORE_DIR)/$(PRODUCT)/*.json; do echo "  $$f:"; cat $$f | $(PYTHON) -m json.tool --indent 2; echo ""; done

score-docs: _require-github-token _require-openrouter-key
	$(PYTHON) scorers/documentation/scorer.py --product-yaml products/$(PRODUCT).yaml

# ── Score all products and rebuild portfolio.json ─────────────────────────────
# Discovers all product YAMLs in products/, scores each one, merges the raw
# scorer outputs into computed/<id>.json, then runs assemble.py to regenerate
# public/portfolio.json — ready for `make dev`.
#
# score-all         — full run including LLM-powered doc checks (needs OPENROUTER_API_KEY)
# score-all-no-llm  — skips AI checks; useful locally without an OpenRouter key

_PRODUCTS := $(patsubst products/%.yaml,%,$(wildcard products/*.yaml))

score-all: _require-github-token _require-openrouter-key
	@echo "Scoring all products: $(_PRODUCTS)"
	@for p in $(_PRODUCTS); do \
		echo ""; \
		echo "── $$p ──────────────────────────────────────────────"; \
		$(MAKE) --no-print-directory score PRODUCT=$$p; \
		$(MAKE) --no-print-directory _merge PRODUCT=$$p; \
	done
	@$(MAKE) --no-print-directory _assemble
	@echo ""
	@echo "Done. public/portfolio.json updated — run 'make dev' to view."

score-all-no-llm: _require-github-token
	@echo "Scoring all products (no LLM): $(_PRODUCTS)"
	@for p in $(_PRODUCTS); do \
		echo ""; \
		echo "── $$p ──────────────────────────────────────────────"; \
		$(MAKE) --no-print-directory score-no-llm PRODUCT=$$p; \
		$(MAKE) --no-print-directory _merge PRODUCT=$$p; \
	done
	@$(MAKE) --no-print-directory _assemble
	@echo ""
	@echo "Done. public/portfolio.json updated — run 'make dev' to view."

# Merge raw scorer output for one product into computed/<id>.json
_merge:
	$(PYTHON) engine/merge_computed.py \
		--product-id $(PRODUCT) \
		--scorers-output-dir $(SCORE_DIR)/$(PRODUCT) \
		--dimensions config/dimensions.yaml \
		--output computed/$(PRODUCT).json
	@echo "  → computed/$(PRODUCT).json updated"

# Rebuild public/portfolio.json from all computed/*.json
_assemble:
	$(PYTHON) engine/assemble.py \
		--products-dir products/ \
		--computed-dir computed/ \
		--dimensions config/dimensions.yaml \
		--drift-history drift-history.json \
		--output public/portfolio.json
	@echo "  → public/portfolio.json updated"

_require-github-token:
	@test -n "$(GITHUB_TOKEN)" || (echo "Error: GITHUB_TOKEN is not set" && exit 1)

_require-openrouter-key:
	@test -n "$(OPENROUTER_API_KEY)" || (echo "Error: OPENROUTER_API_KEY is not set" && exit 1)

# Temporary migration workflow:
# - fetch docs products into a local cache
# - generate a discovery artifact from cached docs + repo PQF products
# Remove the fetch step once the catalog migration no longer needs external docs.
DOCS_PRODUCTS_DIR ?= .pqf-cache/platform-engineering-docs/data/products
DOCS_PRODUCTS_REPO ?= canonical/platform-engineering-docs
DOCS_PRODUCTS_REF ?= main
CATALOG_OVERRIDES_FILE ?=

catalog-discovery: catalog-discovery-fetch catalog-discovery-report

catalog-discovery-fetch:
	$(PYTHON) tools/fetch_platform_engineering_docs_products.py \
		--repo $(DOCS_PRODUCTS_REPO) \
		--ref $(DOCS_PRODUCTS_REF) \
		--output-dir $(DOCS_PRODUCTS_DIR)

catalog-discovery-report:
	$(PYTHON) tools/generate_catalog_discovery.py \
		--docs-products-dir $(DOCS_PRODUCTS_DIR) \
		--pqf-products-dir products \
		--pqf-schema-path config/schemas/product.schema.json \
		--ui-types-path ui/src/types.ts \
		$(if $(CATALOG_OVERRIDES_FILE),--overrides $(CATALOG_OVERRIDES_FILE),) \
		--output docs/superpowers/artifacts/2026-07-20-product-catalog-discovery.json

catalog-import-products: catalog-discovery-fetch
	$(PYTHON) tools/import_platform_engineering_docs_products.py \
		--docs-products-dir $(DOCS_PRODUCTS_DIR) \
		--output-dir products \
		--clean
