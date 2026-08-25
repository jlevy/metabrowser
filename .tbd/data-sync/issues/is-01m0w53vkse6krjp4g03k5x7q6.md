---
type: is
id: is-01m0w53vkse6krjp4g03k5x7q6
title: Validate and document Git revision navigation performance
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T09:48:08.696Z
updated_at: 2026-08-25T10:25:11.766Z
closed_at: 2026-08-25T10:25:11.766Z
close_reason: Validated three interleaved baseline/candidate browser scenarios on one fixed corpus, recorded exp-018, completed manual browser coverage including invalid-route recovery, and passed make verify.
resolution: null
duplicate_of: null
---
Files: explorations/performance-loop/experiments/exp-018-git-revisions-swap-without-blanking.md; explorations/performance-loop/README.md; docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md; docs/project/architecture/arch-views-models-routes.md only if a registered surface changes; docs/development.md or docs/web-performance-framework.md only for a durable cross-feature rule; CHANGELOG.md for the observable navigation improvement. Behavior: alternate at least three visible-Chrome baseline and candidate runs on the same repository/corpus, exercise cold and prepared clicks, and attribute server/data/mount/paint time. Manually test rapid pointer/keyboard traversal, direct routes, error recovery, large/small comparisons, fold state, unified/split layouts, both themes, and reduced motion. Acceptance: target ranges do not overlap or the experiment honestly rejects the optimization; candidate blank duration is zero; max long work, page exceptions, heap, and mounted-resource counts do not regress; docs state measured findings without machine-local paths; make format and focused browser/Python tests pass.
