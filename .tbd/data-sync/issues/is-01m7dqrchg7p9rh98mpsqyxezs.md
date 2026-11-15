---
type: is
id: is-01m7dqrchg7p9rh98mpsqyxezs
title: "Architecture: Git, source sessions and pins, diff pipeline"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmdjvjrgqd3vpqw3z3zdc
created_at: 2026-11-14T19:15:12.048Z
updated_at: 2026-11-15T05:56:39.367Z
---
Phase 2, PR 2: Git and diffs.

- New arch-git.md (about 300 lines): the process boundary, history sessions, graph checkpoints, and commit detail (the history window and commit detail are undescribed today).
- New arch-source-sessions-and-pins.md (about 250): subjects, capabilities, GitPath projection, the pin guard. Copy from the repository document :77-313 (the next PR deletes it there) and the Git document :324-438.
- New arch-diff-pipeline.md (about 200): sources, hydration, caches, Markdown projection. Copy from file-diff-format/diff-sources-and-anchoring.md, the Git document :542-587, and docs/large-content-rendering.md :298-436 (the map-and-entry PR deletes it there). Fold in the design of plan-2026-08-17-general-diff-rendering.md.
- Retire arch-git-and-comparison-sources.md, moving the paths tests/test_git_arch_doc.py reads.

Known errors to fix:
- docs/architecture.md :94-96 and the Git document :537-540 say graph lanes and colors are browser-only; git/wire.py:134-135 and :215 send prior_swimlanes and color_index.
- The Git document :115 says one module creates every git process; build_version.py:60-61 runs git too, and tests/test_git_arch_doc.py:64-74 cannot see it.
- :90-111 describe a generation that nothing produces; :180 says "Four" where five exist; :346-432 repeat 23 lines verbatim; :3-48 is a feature changelog in the status.
- file-diff-format/diff-sources-and-anchoring.md :26-28 "same document" is wrong (diff/adapters/patch_file.py:474-496).
