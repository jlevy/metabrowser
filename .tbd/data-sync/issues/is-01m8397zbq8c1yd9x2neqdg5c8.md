---
type: is
id: is-01m8397zbq8c1yd9x2neqdg5c8
title: "T2: types= narrows a comparison on /api/plugin/diff/comparison and pull-comparison"
kind: task
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m8398r5gb8a7bs9027t38ay5
  - type: blocks
    target: is-01m8398zrcds3cgc9ebm47c9td
  - type: blocks
    target: is-01m839z1p2d8zv8x6hjt31rh0w
parent_id: is-01m83968ry3rs287s3mgg0r93y
hold: null
hold_until: null
created_at: 2026-11-23T04:04:51.701Z
updated_at: 2026-11-23T04:58:16.880Z
started_at: 2026-11-23T04:58:16.873Z
---
`comparison_at` (`builtin_plugins/diff/sidekick.py`) reads `types=` (parsed by
`tree_filter.parse_types`) and narrows the manifest with the T1 matcher, modelled on
`_narrow_to_path`: matching files in comparison order, their patches, and totals of the
narrowed set (exact only when every kept text change is counted). The document stays a
valid file-diff-v1 document. `/api/plugin/github/pull-comparison` gets it by delegation.

- Investigate first: where the list is bounded (`listed()`, the truncation comment near
  line 103) and whether narrowing can run over the files beyond the browser's first
  page. Narrow over everything the server holds; keep `truncated`/`cursor` honest.
- `file=` (deferred hydration of one file) keeps working under a narrowed answer.
- The cache key and the immutable-response rule (`build`/`store` params) include the
  normalized types, so a narrowed answer is cached apart from the whole one.
- Empty token list is the whole comparison, byte-identical to today.
- Parity: a data row `diff.comparison-type-membership` (owner
  `/api/plugin/diff/comparison`, `owned-route`) and a golden, e.g.
  `cli-api-diff-type-filter.tryscript.md`, over a fixture commit mixing .md, .py, a
  rename across types, and a binary file; add the PR route's case to
  `cli-github-pull.tryscript.md`.
