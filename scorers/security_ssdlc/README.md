# Security measurement revisions

`logic.compute_metrics(unit, github_token)` preserves the existing detector rules,
but returns `MetricOutcome` objects and aborts when required GitHub evidence
cannot be acquired. `logic.compute_v0_metrics(unit, github_token)` is the separate
V0 implementation and emits only `renovate_enabled`,
`branch_protection_required_checks`, and `signed_commits_required`.

## V0 evidence conventions

- **Renovate:** parse the supported root/GitHub JSON and JSON5 onboarding files,
  rather than treating filenames, arbitrary code mentions, or automation
  registration as enablement. The V0 gate requires **both enabled onboarding
  configuration and an open bot-authored Dependency Dashboard issue**.
  This grades configured onboarding with bot evidence, **not verified current
  runtime health**. No update-recency threshold, recent-PR alternative, or app
  installation/status API is used.
  A literal object is enabled configuration by default;
  explicit `enabled: false`, `:disableRenovate`, and literal all-package disabling
  rules disable it. Selective package disabling does not disable onboarding.
  Unrelated configuration options are not conformance gates. Follow the approved
  `canonical/renovate-apps` and `canonical/renovate-websites` preset inheritance,
  with bounded cycle detection. Unknown presets or nonliteral configuration
  produce `insufficient_data`, not a positive result. Missing an open dashboard
  is measured false even when configuration is enabled. Enumerate open issues
  with bounded pagination, exclude PRs, and require the exact title
  `Dependency Dashboard` and supported GitHub identity `renovate[bot]`
  (`type: Bot`, user ID `29139614`). A human-created issue with the same title
  is not evidence. Required issue API failures abort acquisition.
- **Classic branch protection:** query the actual default branch, not a presumed
  `main` branch. Require a nonempty check context; acquire the required-signatures
  endpoint when the protection response does not include it. A classic
  protection/signatures 404 means absence. Configured checks and signatures
  count independently of the classic `enforce_admins` policy; this metric does
  not impose a separate administrator-enforcement standard.
- **Rulesets:** include inherited organization rulesets, retrieve their details,
  and evaluate active branch enforcement, default/all-branch selectors, bounded
  literal glob patterns, exclusions, and repository selection. Advisory
  enforcement does not count. Any documented bypass permits an exception and
  therefore does not establish a universal requirement. A missing bypass list
  is insufficient evidence: GitHub hides it from readers without write access.
  Independently sufficient protection can establish a requirement despite an
  unrelated uninterpretable rule.
- **Failures:** authentication, authorization, rate-limit, and server errors
  after supported shared retries raise `GitHubAcquisitionError`. Do not turn
  them into negative measurements or empty evidence. Missing repository context
  is `not_applicable`; successfully acquired absent signals are measured false.

## Authorities inspected

- `canonical/platform-engineering-docs`, engineering practices /
  security practices / keep dependencies updated with Renovate.
- `canonical/renovate-apps/default.json` and
  `canonical/renovate-websites/default.json`.
- `canonical/canonical-repo-automation/modules/repo/main.tf` and the Platform
  Engineering repository settings/templates. These HCL conventions grant
  Renovate permission to push or bypass selected rules; they do **not** configure
  or enable dependency updates. Neither a registration path nor the Renovate
  app ID (`2740`) in those grants is counted as onboarding.

Run the scoped tests with:

```sh
PYTEST_ADDOPTS='scorers/security_ssdlc/__tests__ -q' make test
```
