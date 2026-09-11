# Run PQF locally

Use this workflow to preview changes to metric logic, medal criteria, or product definitions
without waiting for the nightly GitHub Actions run.

## Set up once

```bash
python3 -m venv venv
source venv/bin/activate
make install-all
gh auth login
```

`make install-all` runs two existing setup targets:

- `make install` installs PQF in editable mode plus its Python test, lint, and validation
  dependencies into the active Python environment. The virtual environment above keeps them out
  of your system Python.
- `make install-ui` runs `npm install` in `ui/`, placing the dashboard dependencies in
  `ui/node_modules/`. It does not install global npm packages.

The Makefile reads `GITHUB_TOKEN` from `gh auth token`, so you do not need to export it.

## Choose a framework version

Local scoring now runs against an explicit framework contract under `framework/versions/<id>/`.
Every runtime command must receive `FRAMEWORK_VERSION=<id>`; there is no unversioned contract and
nothing defaults to a version.

- **Active** and **upcoming** framework versions can be scored, merged, and assembled locally.
- **Archived** framework versions are frozen snapshots. Local scoring rejects them instead of
  recomputing them.
- Published data refreshes on different cadences: the **active** version refreshes nightly and the
  **upcoming** version refreshes weekly. Locally you can regenerate either eligible version on
  demand.

## Run the local loop

Pick a representative product ID from `products/`, then run:

```bash
make score-no-llm PRODUCT=matrix FRAMEWORK_VERSION=v1
make _merge PRODUCT=matrix FRAMEWORK_VERSION=v1
make _assemble FRAMEWORK_VERSION=v1
make _version-index
```

In a second terminal, start the dashboard:

```bash
make dev
```

Open <http://localhost:5173>. Keep the dev server running while you repeat the scoring commands;
it reloads the rebuilt versioned portfolio data automatically.

`make _version-index` rebuilds `public/framework-versions.json`. Run it after the active and
upcoming local portfolios both exist under `public/versions/`, otherwise the index will fail fast
because active/upcoming entries must stay in sync with their published contracts.

## What to rerun after a change

| Change | Rerun |
|--------|-------|
| `scorers/<dimension>/logic.py` | Targeted scorer tests, then the local loop above |
| `products/<id>.yaml` | The local loop above for that product |
| Result criteria in `framework/versions/<id>/dimensions.yaml` | `make validate && make _assemble FRAMEWORK_VERSION=<id>` |
| Output keys or `required_metrics_for_scoring` | The local loop above because computed data must be regenerated |
| AI metric or prompt | Use the AI variation below |

`make _assemble FRAMEWORK_VERSION=<id>` can reuse existing
`computed/versions/<id>/*.json` only when scorer output keys and nullability are unchanged.

> **Keep measured-low separate from unmeasurable.** `false`, `0`, or a low percentage is a real
> result and should be scored. Use `null` only when the signal could not be measured; a required
> metric with a `null` value makes the dimension `insufficient_data` and `unrated`.

## Include AI-assisted metrics

The default loop skips the AI-assisted documentation check. To exercise that metric, export an
OpenRouter key and replace the first command with `make score`:

```bash
export OPENROUTER_API_KEY=<your-key>
make score PRODUCT=matrix FRAMEWORK_VERSION=v1
make _merge PRODUCT=matrix FRAMEWORK_VERSION=v1
make _assemble FRAMEWORK_VERSION=v1
```

Set `OPENROUTER_MODEL` only when you need to test a model other than the repository default:

```bash
export OPENROUTER_MODEL=<openrouter-model-id>
```

Current medal gates are deterministic, so most scorer, rubric, and product changes should use
the default no-AI loop.

## Inspect the result

- `.pqf-score/<framework>/<id>/*.json`: raw output from each scorer for one framework version
- `computed/versions/<framework>/<id>.json`: merged metrics for the product and its leaf components
- `public/versions/<framework>/portfolio.json`: assembled results and medal assignments for that framework
- `public/framework-versions.json`: active/upcoming/archive index consumed by the UI version selector

Use `make score-all-no-llm FRAMEWORK_VERSION=v1` only when you need to compare the whole
portfolio. Use `make score-all FRAMEWORK_VERSION=v1` for the same comparison with AI-assisted
metrics enabled.

## Keep generated previews out of commits

Local scoring rewrites versioned artifacts under `computed/versions/`, `public/versions/`, and
`public/framework-versions.json` so the dashboard can show your changes. These files are maintained
by GitHub Actions: inspect them locally, but do not hand-edit or commit them. Commit the source
change in `scorers/`, `framework/versions/`, or `products/` instead.
