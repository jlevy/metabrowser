---
type: is
id: is-01m8397pq43tfbxt7vbn8hp2wv
title: "T1: One file-type matcher shared by the Files tree and diff narrowing"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m8397zbq8c1yd9x2neqdg5c8
  - type: blocks
    target: is-01m83989qdepvtpwd91pqdr5er
parent_id: is-01m83968ry3rs287s3mgg0r93y
created_at: 2026-11-23T04:04:42.850Z
updated_at: 2026-11-23T04:05:53.838Z
---
Move `_matches_types`, `_semantic_extension_tokens`, and the basename/tail-extension
helpers they use out of `git/content_routes.py` into a shared module (beside
`tree_filter.py` / `file_type_filters.py`), taking a display path rather than a
`GitPath`, so the Files tree on a revision and the diff narrowing (T2) apply one rule.

- `tree_filter.parse_types` stays the one parser of the `types=` vocabulary.
- Add a FileChange-level helper: a change matches when its new side or its old side
  matches (epic decision 3).
- No behavior change for the Files tree: existing git content route tests and goldens
  stay green unchanged.
- Unit tests: dotted logical extensions, semantic tokens (`.d.ts` under `.ts`), bare
  filename tokens (`makefile`), case folding, renames across types, added/deleted sides.
