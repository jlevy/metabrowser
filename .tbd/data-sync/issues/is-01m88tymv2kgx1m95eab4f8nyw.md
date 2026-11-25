---
type: is
id: is-01m88tymv2kgx1m95eab4f8nyw
title: "PR #822 A8: a step answer's wait on the Markdown child is unmeasured"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m88tv745atsmky56h05dnn0f
hold: null
hold_until: null
created_at: 2026-11-25T07:50:32.542Z
updated_at: 2026-11-25T08:58:01.513Z
started_at: 2026-11-25T07:51:53.855Z
closed_at: 2026-11-25T08:58:01.508Z
close_reason: "Fixed in d067c9779: the notes wait is measured cold and warm and recorded beside _rendered_note. PR #822 review A dispositions: https://github.com/jlevy/metabrowser/pull/822#issuecomment-7157686246"
resolution: null
duplicate_of: null
---
guided_review.py:1077-1080 awaits up to two renders in the shared child (markdown_projection_worker.py:225-236), cold start up to _START_WAIT_S; measure cold and warm and record beside _rendered_note. Severity: Low. PR #822, review A: https://github.com/jlevy/metabrowser/pull/822#pullrequestreview-6053614872
