# Testing measurement revisions

`logic.compute_metrics(unit, github_token=None)` retains the previous six-output
measurement algorithm, including its Allure/default-branch fallback and search
detectors. It now wraps every result in `MetricOutcome`; unavailable legacy
numeric/CI results are `insufficient_data`, not null scalars. Keep immutable
implementation revisions bound to this runner.

The target runner is:

```python
compute_v0_metrics(
    unit: EvaluationUnit,
    github_token: str | None = None,
    *,
    juju4_track: str = "4/stable",
    juju_lts_track: str = "3.6/stable",
) -> dict[str, MetricOutcome]
```

It returns exactly `uses_ops_testing`, `uses_jubilant`,
`uses_charm_ci`, `uses_gh_runners_unit_testing`, `uses_tf_v1_provider`,
`supports_canonical_k8s`, `supports_juju_4`, and `supports_juju_lts`.
All values are structured outcomes. Contract parameters pin the two
stable Juju tracks rather than resolving moving releases inside the scorer. A
major-only track (`4/stable`) accepts any stable release in that line
(`4.0/stable`, `4.1/stable`); a pinned track (`3.6/stable`) must match exactly.

## Evidence and boundaries

* `evidence.py` acquires a GitHub default-branch tip, its recursive tree and
  immutable blobs. Truncated trees and failed GitHub requests fail the
  runner. GitHub helpers perform their existing supported authentication retry.
* `v0.py` is pure. Ops Testing positive imports and deprecated Harness
  references are scoped exclusively to the component's `tests/unit`;
  Jubilant imports are independently scoped to `tests/integration`.
  Nested charms cannot supply another charm's tests or Terraform modules.
* A charm unit with no `charmcraft.yaml`/`metadata.yaml` at its configured
  path makes every charm metric insufficient, surfacing a wrong product
  `subpath` instead of reporting false non-compliance.
* Workflows require parsed job-level reusable calls. Supported integration
  names are `canonical/charm-ci/.github/workflows/integration-test.yml` and
  equivalent underscore/plural/YAML spellings. Build-only calls and incidental
  text do not qualify.
* Unit evidence is a scoped operator-workflows `test.yaml` call or a local
  `tox -e unit`/`unit-tests` or `pytest tests/unit` invocation, including
  `python -m` and `uv run` wrappers. `working-directory`, not
  `charm-directory`, controls operator-workflows unit-test scope.
  Literal matrices (including `matrix.<axis>.<property>` objects) are
  expanded; dynamic directories/runners are insufficient. An unresolvable job
  only blocks the metric when it calls the unit workflow or runs `tox`/`pytest`.
  Every identified unit-test job must use a known GitHub-hosted label.
* Configuration evidence comes only from matching charm-ci calls and
  active Spread integration suites whose
  `working-dir` and test location (`discover-path`, else the suite path) match
  the component; suite keys are free-form names. Root Spread configuration
  can link shared configuration to an explicit component suite. Unused
  Concierge files and sibling suites do not count. Spread `CONCIERGE` and
  `CONCIERGE/<variant>` environment paths are supported, cascading project →
  backend → suite. A `spread-jobs-include` filter is fnmatched, as opcli does,
  against `<backend>-ci:<system>:build/<suite>/run:<variant>` selectors.
  Auto-discovered module variants are represented by sentinel names; a filter
  selecting only some variants is insufficient. Invented inputs such
  as `juju-channel` or `concierge-config` do not count: the reusable workflow
  does not consume them. An unresolved dynamic path/filter is insufficient.
  The canonical `$(HOST: echo "${CONCIERGE:-path.yaml}")` spelling is parsed
  strictly as a configured default path, never executed.
* K8s applicability uses scoped `containers`, `assumes: k8s-api` (including
  `any-of`/`all-of`), legacy `series: kubernetes`, and known K8s framework
  extensions. Machine charms are not applicable. Only an enabled, bootstrapped
  linked `providers.k8s` qualifies; MicroK8s does not.
* `terraform.py` parses literal HCL/JSON `required_providers` declarations,
  including aliases and comments. Juju requirements must explicitly identify
  `juju/juju` or `registry.terraform.io/juju/juju`; the local alias can be
  arbitrary. An omitted source defaults to `hashicorp/juju` and does not qualify.
  All component modules must declare a Juju
  requirement restricted to major 1: exact, pessimistic (`~>`), or bounded
  comparison constraints. An unbounded `>= 1.0` does **not** restrict major
  versions to 1. Unsupported/dynamic expressions and contradictory ranges
  are insufficient; missing requirements are measured false; no modules is
  not applicable.

All eight charm-only metrics are not applicable to snaps. Missing required
test/workflow/configuration evidence is measured false, rather than adoption by
empty iteration. Ops Testing requires a positive scoped `ops.testing` import
and absence of deprecated Harness references. Missing tests or imports returns
false. No integration tests means Jubilant is false.

Runner source fingerprints must include `logic.py`, `evidence.py`, `v0.py`,
`terraform.py`, and the imported shared GitHub helper source, plus the engine
outcome/model definitions under the registry's normal dependency policy.

## Validation

```bash
PYTEST_ADDOPTS="scorers/test_verification/__tests__ -q" make test
```

Tests mock HTTP acquisition, cover published-track CI and merged-PR identity,
reruns/statuses/required checks/pagination, component isolation, AST imports,
runner matrices, linked Concierge configuration and Terraform constraints.
