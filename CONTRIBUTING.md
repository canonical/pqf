# Contributing to PQF

---

## Prerequisites

- Python 3.12+
- Node.js 22+
- `gh` CLI (authenticated: `gh auth login`)

---

## Local setup

```bash
git clone https://github.com/srbouffard/pqf.git
cd pqf
make install-all   # Python deps + Node deps
```

---

## Running tests

```bash
make test          # Python unit tests (110 tests, ~2s)
make test-ui       # Vitest UI unit tests
make test-all      # Both
make lint          # Python ruff lint
make format        # Auto-format Python
```

The CI runs these same commands — if it passes locally, it will pass in CI.

---

## Running the UI locally

```bash
make dev           # Starts Vite dev server at http://localhost:5173
```

The UI reads `public/portfolio.json` at startup. To see real data, the file is already present in the repo (regenerated nightly by GHA). You don't need to run the scorers to develop the UI.

To change metric logic, medal criteria, or product definitions and preview the result, follow
[Run PQF locally](docs/local-scoring.md). The default workflow does not require an AI API key.

---

## What's auto-generated vs manually maintained

| File / Directory | Maintained by | Edit? |
|-----------------|---------------|-------|
| `products/*.yaml` | PE team, PR-reviewed | ✅ Yes |
| `config/dimensions.yaml` | Contributors, PR-reviewed | ✅ Yes |
| `computed/*.json` | GHA nightly scorer | ❌ Never |
| `public/portfolio.json` | GHA nightly scorer | ❌ Never |
| `public/badges/` | GHA nightly scorer | ❌ Never |
| `drift-history.json` | GHA drift tracker | ❌ Never |

---

## PR workflow

1. **Branch:** `feat/my-feature` or `fix/my-fix` (no ticket prefix required)
2. **Commits:** Conventional Commits — `feat:`, `fix:`, `docs:`, `chore:`
3. **PR title:** Mirrors your commit subject (the CI enforces nothing, but reviewers appreciate consistency)
4. **CI checks:** Python lint, Python tests, UI tests, security audit — all must pass

---

## Adding a product

See [docs/adding-a-product.md](docs/adding-a-product.md).

---

## Adding a quality dimension / scorer

See [docs/adding-a-dimension.md](docs/adding-a-dimension.md).

---

## Code style

**Python:** `ruff` for linting and formatting. Config in `pyproject.toml`. Line length 100, target Python 3.11+.

```bash
make lint          # Check
make format        # Fix
```

**TypeScript:** ESLint via Vite. Run with:
```bash
cd ui && npm run lint
```

No Tailwind, no shadcn. All UI components use `@canonical/react-components` (Vanilla Framework wrappers).
