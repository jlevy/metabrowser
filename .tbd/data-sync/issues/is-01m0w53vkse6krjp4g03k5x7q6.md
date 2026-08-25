---
type: is
id: is-01m0w53vkse6krjp4g03k5x7q6
title: Validate and document Git revision navigation performance
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
  - type: blocks
    target: is-01m0wq55zyfz7g5r55k9h6ntyv
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T09:48:08.696Z
updated_at: 2026-08-25T15:04:21.836Z
closed_at: 2026-08-25T10:25:11.766Z
close_reason: Validated three interleaved baseline/candidate browser scenarios on one fixed corpus, recorded exp-018, completed manual browser coverage including invalid-route recovery, and passed make verify.
resolution: null
duplicate_of: null
---
Files: explorations/performance-loop/experiments/exp-018-git-revisions-swap-without-blanking.md; explorations/performance-loop/README.md; docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md; docs/project/specs/active/plan-2026-08-21-load-time-performance.md; docs/web-performance-framework.md; CHANGELOG.md; docs/project/architecture/arch-views-models-routes.md only if a registered surface changes. Behavior: alternate at least three visible-Chrome baseline and candidate runs with product builds and corpus frozen independently; attribute server, transfer/decode, mount, painted-ready, and continuity costs; use measured comparison volume to accept one-slot intent prefetch and reject all-visible prefetch. Acceptance: candidate blank frames are zero; only nonoverlapping targets support a speed claim; cold overlap is disclosed; long work, page exceptions, heap, and mounted resources do not regress; manual tests cover rapid pointer/keyboard selection, direct and invalid routes with recovery, small/large comparisons, folds, unified/split, themes, and reduced motion; focused tests, make format, and make verify pass; public docs contain no local paths.
