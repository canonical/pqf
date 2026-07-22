Task 2 report: Rewrite config/dimensions.yaml to the new rubric contract

What I implemented
- Rewrote config/dimensions.yaml in the pqf-dimension-rubric-redesign worktree to match the new rubric contract specified in the task brief and human clarifications. Changes include:
  - Replaced test_verification, documentation, substrate_compat, security_ssdlc, support_engagement blocks with new outputs and medals per spec.
  - Added new documentation metrics: readme_meets_structure, contributing_meets_structure, documentation_workflows_passing, tutorial_tested, uses_rtd_hosting, recent_release_notes_present, and updated diataxis_coverage description to be deterministic.
  - Replaced security_ssdlc outputs to renovate_enabled, canonical_repo_automation_registered, sast_workflow_present, cve_tracking_process_present, and updated medals accordingly.

What I tested and test results
- Followed TDD as required.
- RED: Ran the focused test inside the worktree before changes; observed failure asserting presence of renovate_enabled etc.
  - Command: (cd .worktrees/pqf-dimension-rubric-redesign && pytest -q scorers/security_ssdlc/__tests__/test_logic.py -k dimensions_yaml_mentions_new_ssdlc_metrics -q)
  - Output: Failed as expected (AssertionError for missing renovate_enabled)
- GREEN: Implemented changes and re-ran the focused test.
  - Command: (cd .worktrees/pqf-dimension-rubric-redesign && pytest -q scorers/security_ssdlc/__tests__/test_logic.py -q)
  - Output: 7 passed in 0.12s

TDD evidence
- RED command/output (failing):
  (cd .worktrees/pqf-dimension-rubric-redesign && pytest -q scorers/security_ssdlc/__tests__/test_logic.py -k dimensions_yaml_mentions_new_ssdlc_metrics -q)
  -> Failure: AssertionError: 'renovate_enabled' not in outputs

- GREEN command/output (passing):
  (cd .worktrees/pqf-dimension-rubric-redesign && pytest -q scorers/security_ssdlc/__tests__/test_logic.py -q)
  -> 7 passed in 0.12s

Files changed
- Modified: .worktrees/pqf-dimension-rubric-redesign/config/dimensions.yaml
- Modified: .worktrees/pqf-dimension-rubric-redesign/scorers/security_ssdlc/__tests__/test_logic.py (test appended as requested)

Self-review findings
- I followed the brief and the human clarifications exactly for metric names and medal mapping.
- I ensured AI-assisted metrics remain informational by description and not included in medal criteria, per instructions.
- I replaced the documentation diataxis description to be deterministic (count-only).

Issues or concerns
- No functional code changes to scorers were made; only config. Downstream scorers must be updated to compute the new metric names/semantics.
- I committed the test change and config in the worktree (branch pqf-dimension-rubric-redesign). Ensure PR merges to main.

Report file path
.superpowers/sdd/task-2-report.md

Fixes applied after review feedback

- Removed unintended .gitignore entries for .superpowers
- Commit: fix: remove accidental .superpowers ignore entry (4156adc)
- Re-ran covering test:
  - pytest scorers/security_ssdlc/__tests__/test_logic.py -v -k dimensions_yaml_mentions_new_ssdlc_metrics -> 1 passed
- Ran make validate:
  - Result: FAILED (validation errors in config/dimensions.yaml: missing required properties `label`, `description`, `scorer`, `applies_to`, `aggregation` for multiple dimensions)

Next steps

- The config now contains the correct output and medals per Task 2, but must be augmented with the standard dimension metadata (label, description, scorer, applies_to, aggregation) so engine.validate passes.

Fix applied

- Added required dimension metadata fields (label, description, scorer, applies_to, aggregation) to all five dimensions in config/dimensions.yaml.
- Scorer paths reused from existing repo: scorers/test_verification/scorer.py, scorers/documentation/scorer.py, scorers/substrate_compat/scorer.py, scorers/security_ssdlc/scorer.py, scorers/support_engagement/scorer.py.
- Applies_to choices:
  - test_verification: ["charm","snap"]
  - documentation: ["charm","snap"]
  - substrate_compat: ["charm"]
  - security_ssdlc: ["charm","snap"]
  - support_engagement: ["root","charm","snap"]
- aggregation: set to "worst_in_scope" for all dimensions.

Validation & tests

- Focused pytest: scorers/security_ssdlc/__tests__/test_logic.py -k dimensions_yaml_mentions_new_ssdlc_metrics -> PASSED (1 test)
- make validate -> PASSED (All files valid)

Commit

- Created commit: 0d936f1 feat(rubric): add required dimension metadata (label, description, scorer, applies_to, aggregation)

Concerns

- Downstream scorers still emit older metric keys (e.g., dependabot_enabled/codeql_enabled) in public artifacts; scorers need updating to produce the new security_ssdlc metrics to make computed outputs consistent with the new rubric.

Report file path

.superpowers/sdd/task-2-report.md

