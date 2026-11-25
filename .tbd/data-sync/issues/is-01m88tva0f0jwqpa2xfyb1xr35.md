---
type: is
id: is-01m88tva0f0jwqpa2xfyb1xr35
title: "PR #822 A1: a refused note render is silent and kept for the record revision"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m88tv745atsmky56h05dnn0f
hold: null
hold_until: null
created_at: 2026-11-25T07:48:43.148Z
updated_at: 2026-11-25T08:57:41.137Z
started_at: 2026-11-25T07:51:15.577Z
closed_at: 2026-11-25T08:57:41.133Z
close_reason: "Fixed in d067c9779 and 5f7b5e616: the route answers note_refusal/group_note_refusal, the page draws textRefusalNote's line under the typed note and keeps no busy/unavailable answer. PR #822 review A dispositions: https://github.com/jlevy/metabrowser/pull/822#issuecomment-7157686246"
resolution: null
duplicate_of: null
---
guided_review.py:975-983 _rendered_note drops refused.code; guided-review.js:277-306 shows the note as typed with nothing said; the page keeps step answers per revision (guided-review.js:69, 86-99), so a transient busy/unavailable refusal stays as raw source. Against docs/design-system.md:3078 and docs/design-system-messages.md:38,140; plan-2026-11-24-stack-review.md:152 claims 'as a description does'. Severity: Medium. PR #822, review A: https://github.com/jlevy/metabrowser/pull/822#pullrequestreview-6053614872
