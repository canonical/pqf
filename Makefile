# PQF — Product Quality Framework
# Usage: make <target>
# All Python targets assume the venv/dev deps are installed: make install
# All UI targets run inside ui/

.DEFAULT_GOAL := help
.PHONY: help install install-ui install-all \
	lint format format-check ci-check \
	validate \
	test test-ui test-all \
	build dev \
	audit audit-python audit-ui \
	score score-docs score-no-llm _score-product \
	score-all score-all-no-llm _merge _assemble _version-index \
	e2e _require-github-token _require-openrouter-key \
	catalog-discovery catalog-discovery-fetch catalog-discovery-report \
	catalog-import-products

PYTHON := python3
PIP    := pip
NPM    := npm
SCORE_DIR := .pqf-score
FRAMEWORK_ROOT := framework/versions
FRAMEWORK_VERSION ?= $(error FRAMEWORK_VERSION is required. Example: FRAMEWORK_VERSION=v1)
FRAMEWORK_DIR = $(FRAMEWORK_ROOT)/$(FRAMEWORK_VERSION)
VERSION_SCORE_DIR = $(SCORE_DIR)/$(FRAMEWORK_VERSION)/$(PRODUCT)
VERSION_COMPUTED_DIR = computed/versions/$(FRAMEWORK_VERSION)
VERSION_PUBLIC_DIR = public/versions/$(FRAMEWORK_VERSION)
SOURCE_REVISION ?=

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
	@echo "    make ci-check       Run everything CI runs: lint + format-check + test + test-ui"
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
	@echo "    make score PRODUCT=<id> FRAMEWORK_VERSION=<id>        Score one product (all dimensions, with LLM)"
	@echo "    make score-no-llm PRODUCT=<id> FRAMEWORK_VERSION=<id> Score one product (skip AI doc checks)"
	@echo "    make score-docs PRODUCT=<id> FRAMEWORK_VERSION=<id>   Run only the documentation scorer"
	@echo "    make score-all FRAMEWORK_VERSION=<id>                 Score all products for one framework (with LLM)"
	@echo "    make score-all-no-llm FRAMEWORK_VERSION=<id>          Score all products for one framework (no LLM)"
	@echo "    make _version-index                                   Rebuild public/framework-versions.json"
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

ci-check: lint format-check test test-ui

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

score: SCORE_RUNNER_ENV =
score: SCORE_MESSAGE = Scoring product: $(PRODUCT) for framework $(FRAMEWORK_VERSION)
score: _require-github-token _require-openrouter-key _score-product

score-no-llm: SCORE_RUNNER_ENV = OPENROUTER_API_KEY=
score-no-llm: SCORE_MESSAGE = Scoring product: $(PRODUCT) for framework $(FRAMEWORK_VERSION) (LLM checks skipped — diataxis/style will be 0/false)
score-no-llm: _require-github-token _score-product

_score-product:
	@echo "$(SCORE_MESSAGE)"
	@mkdir -p $(VERSION_SCORE_DIR)
	@set -e; \
	dimensions="$$( $(PYTHON) -m engine.framework --root $(FRAMEWORK_ROOT) --version $(FRAMEWORK_VERSION) --list-dimensions )"; \
	for dimension in $$dimensions; do \
		$(SCORE_RUNNER_ENV) $(PYTHON) scorers/run.py \
			--framework-root $(FRAMEWORK_ROOT) \
			--framework-version $(FRAMEWORK_VERSION) \
			--dimension $$dimension \
			--product-yaml products/$(PRODUCT).yaml \
			--products-dir products/ \
			> $(VERSION_SCORE_DIR)/$$dimension.json; \
	done
	@echo ""
	@echo "Results in $(VERSION_SCORE_DIR)/"
	@for f in $(VERSION_SCORE_DIR)/*.json; do echo "  $$f:"; cat $$f | $(PYTHON) -m json.tool --indent 2; echo ""; done

score-docs: _require-github-token _require-openrouter-key
	@mkdir -p $(VERSION_SCORE_DIR)
	$(PYTHON) scorers/run.py \
		--framework-root $(FRAMEWORK_ROOT) \
		--framework-version $(FRAMEWORK_VERSION) \
		--dimension documentation \
		--product-yaml products/$(PRODUCT).yaml \
		--products-dir products/ \
		> $(VERSION_SCORE_DIR)/documentation.json
	@echo "Results in $(VERSION_SCORE_DIR)/documentation.json"

# ── Score all products and rebuild one versioned portfolio ────────────────────
# Discovers all product YAMLs in products/, scores each one, merges the raw
# scorer outputs into computed/versions/<framework>/<id>.json, then runs
# assemble.py to regenerate public/versions/<framework>/portfolio.json.
#
# score-all         — full run including LLM-powered doc checks (needs OPENROUTER_API_KEY)
# score-all-no-llm  — skips AI checks; useful locally without an OpenRouter key

_PRODUCTS := $(patsubst products/%.yaml,%,$(wildcard products/*.yaml))

score-all: _require-github-token _require-openrouter-key
	@echo "Scoring all products for framework $(FRAMEWORK_VERSION): $(_PRODUCTS)"
	@for p in $(_PRODUCTS); do \
		echo ""; \
		echo "── $$p ──────────────────────────────────────────────"; \
		$(MAKE) --no-print-directory score PRODUCT=$$p FRAMEWORK_VERSION=$(FRAMEWORK_VERSION); \
		$(MAKE) --no-print-directory _merge PRODUCT=$$p FRAMEWORK_VERSION=$(FRAMEWORK_VERSION); \
	done
	@$(MAKE) --no-print-directory _assemble FRAMEWORK_VERSION=$(FRAMEWORK_VERSION)
	@echo ""
	@echo "Done. $(VERSION_PUBLIC_DIR)/portfolio.json updated."

score-all-no-llm: _require-github-token
	@echo "Scoring all products for framework $(FRAMEWORK_VERSION) (no LLM): $(_PRODUCTS)"
	@for p in $(_PRODUCTS); do \
		echo ""; \
		echo "── $$p ──────────────────────────────────────────────"; \
		$(MAKE) --no-print-directory score-no-llm PRODUCT=$$p FRAMEWORK_VERSION=$(FRAMEWORK_VERSION); \
		$(MAKE) --no-print-directory _merge PRODUCT=$$p FRAMEWORK_VERSION=$(FRAMEWORK_VERSION); \
	done
	@$(MAKE) --no-print-directory _assemble FRAMEWORK_VERSION=$(FRAMEWORK_VERSION)
	@echo ""
	@echo "Done. $(VERSION_PUBLIC_DIR)/portfolio.json updated."

# Merge raw scorer output for one product into computed/versions/<version>/<id>.json
_merge:
	@set -e; \
	contract_digest="$$($(PYTHON) -c 'from pathlib import Path; from engine.framework import contract_digest, discover_frameworks, get_framework; framework = get_framework(discover_frameworks(Path("$(FRAMEWORK_ROOT)")), "$(FRAMEWORK_VERSION)"); print(contract_digest(framework))')"; \
	implementation_fingerprints="$$($(PYTHON) -c 'from pathlib import Path; import json; from engine.framework import discover_frameworks, get_framework; from scorers.registry import implementation_fingerprints; framework = get_framework(discover_frameworks(Path("$(FRAMEWORK_ROOT)")), "$(FRAMEWORK_VERSION)"); fingerprints = {}; [fingerprints.update(implementation_fingerprints(dim_cfg)) for dim_cfg in framework.dimensions["dimensions"].values()]; print(json.dumps(fingerprints, sort_keys=True))')"; \
	$(PYTHON) engine/merge_computed.py \
		--product-id $(PRODUCT) \
		--scorers-output-dir $(VERSION_SCORE_DIR) \
		--dimensions $(FRAMEWORK_DIR)/dimensions.yaml \
		--framework-version $(FRAMEWORK_VERSION) \
		--contract-digest "$$contract_digest" \
		--implementation-fingerprints "$$implementation_fingerprints" \
		--output $(VERSION_COMPUTED_DIR)/$(PRODUCT).json
	@echo "  → $(VERSION_COMPUTED_DIR)/$(PRODUCT).json updated"

# Rebuild public/versions/<version>/portfolio.json from computed/versions/<version>/*.json
_assemble:
	@set -e; \
	source_revision="$(SOURCE_REVISION)"; \
	if [ -z "$$source_revision" ]; then \
		source_revision="$$(git --no-pager rev-parse HEAD)"; \
	fi; \
	$(PYTHON) engine/assemble.py \
		--products-dir products/ \
		--computed-dir computed/ \
		--framework-root $(FRAMEWORK_ROOT) \
		--framework-version $(FRAMEWORK_VERSION) \
		--source-revision "$$source_revision" \
		--output $(VERSION_PUBLIC_DIR)/portfolio.json
	@echo "  → $(VERSION_PUBLIC_DIR)/portfolio.json updated"

_version-index:
	$(PYTHON) engine/version_index.py \
		--framework-root $(FRAMEWORK_ROOT) \
		--public-dir public/ \
		--output public/framework-versions.json
	@echo "  → public/framework-versions.json updated"

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
