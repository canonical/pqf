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

## Run the local loop

Pick a representative product ID from `products/`, then run:

```bash
make score-no-llm PRODUCT=matrix
make _merge PRODUCT=matrix
make _assemble
```

In a second terminal, start the dashboard:

```bash
make dev
```

Open <http://localhost:5173>. Keep the dev server running while you repeat the scoring commands;
it reloads the rebuilt `public/portfolio.json` automatically.

## What to rerun after a change

| Change | Rerun |
|--------|-------|
| `scorers/<dimension>/logic.py` | Targeted scorer tests, then the local loop above |
| `products/<id>.yaml` | The local loop above for that product |
| Medal criteria in `config/dimensions.yaml` | `make validate && make _assemble` |
| Output keys or `required_metrics_for_scoring` | The local loop above because computed data must be regenerated |
| AI metric or prompt | Use the AI variation below |

`make _assemble` can reuse existing `computed/*.json` only when scorer output keys and nullability
are unchanged.

> **Keep measured-low separate from unmeasurable.** `false`, `0`, or a low percentage is a real
> result and should be scored. Use `null` only when the signal could not be measured; a required
> metric with a `null` value makes the dimension `insufficient_data` and `unrated`.

## Include AI-assisted metrics

The default loop skips the AI-assisted documentation check. To exercise that metric, export an
OpenRouter key and replace the first command with `make score`:

```bash
export OPENROUTER_API_KEY=<your-key>
make score PRODUCT=matrix
make _merge PRODUCT=matrix
make _assemble
```

Set `OPENROUTER_MODEL` only when you need to test a model other than the repository default:

```bash
export OPENROUTER_MODEL=<openrouter-model-id>
```

Current medal gates are deterministic, so most scorer, rubric, and product changes should use
the default no-AI loop.

## Inspect the result

- `.pqf-score/<id>/*.json`: raw output from each scorer
- `computed/<id>.json`: merged metrics for the product and its leaf components
- `public/portfolio.json`: assembled results and medal assignments consumed by the UI

Use `make score-all-no-llm` only when you need to compare the whole portfolio. Use
`make score-all` for the same comparison with AI-assisted metrics enabled.

## Keep generated previews out of commits

Local scoring rewrites `computed/<id>.json` and `public/portfolio.json` so the dashboard can show
your changes. These files are maintained by GitHub Actions: inspect them locally, but do not
hand-edit or commit them. Commit the source change in `scorers/`, `config/`, or `products/`
instead.
