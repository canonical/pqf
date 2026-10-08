### Metric name

*Use a short, plain-language name.*

**Proposed ID:** `snake_case_metric_id`\
**Dimension:** *Existing dimension, or proposed new dimension*\
**Status:** *Graded or informational only*\
**Applies to:** *For example: all products, charms, snaps, K8s charms, or products with user-facing documentation*

#### What it measures

*In one or two sentences, describe the practice or quality signal this metric represents. Explain why teams should align on it, not how the detector works.*

#### Measurement

*Describe the evidence PQF should inspect and the decision it should make. Be specific enough that an engineer could implement the measurement without guessing.*

1. *Where should PQF look?*\
2. *What evidence produces a passing result?*\
3. *What evidence produces a failing result?*\
4. *When should the result be insufficient data?*\
5. *When should the metric be not applicable?*

#### Accepted variations

*List only legitimate structural or tooling differences that the measurement must support. Do not list arbitrary repository-specific exceptions.*

- *For example: monorepo configuration may be at the root or within the component subpath.*\
- *For example: CI may be defined locally or through an approved shared workflow.*

#### Proposed medal placement

| Grade | Proposed requirement |
| :---- | :---- |
| Bronze / Silver / Gold | *Where should this metric enter the dimension rubric, and why?* |

*For an informational metric, state that it does not affect medals and delete the table.*

#### Evidence and examples

*Link to representative repositories, workflows, standards or guidance. Include at least one example that should pass and, when useful, one that should fail.*

- **Should pass:** *link and brief reason*\
- **Should fail:** *link and brief reason*

#### Open questions

*List only decisions the team must make before accepting the metric. Delete this section when there are none.*

- *Question*

---
