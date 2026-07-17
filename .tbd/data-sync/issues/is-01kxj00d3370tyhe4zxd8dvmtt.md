---
type: is
id: is-01kxj00d3370tyhe4zxd8dvmtt
title: "PR #1 review B3: make manual browser checklist runnable"
kind: bug
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:22.850Z
updated_at: 2026-07-17T21:16:38.180Z
closed_at: 2026-07-15T06:02:32.479Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Fresh end-to-end review R3: docs point at tests/fixtures, which lacks the Markdown, structured, JSONL, image, and binary artifacts named by the checklist. Add a public-safe manual fixture corpus and align all commands and expected checks.

## Notes

Added a seven-file public-safe manual corpus. A running source checkout rendered Markdown, structured, source, JSONL, SVG, and binary views; direct links, live create/delete, Recent, themes, 480px layout, focus, print handoff, and zero console warnings/errors were verified.
