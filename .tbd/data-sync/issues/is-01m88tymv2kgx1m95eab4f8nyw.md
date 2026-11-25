---
type: is
id: is-01m88tymv2kgx1m95eab4f8nyw
title: "PR #822 A8: a step answer's wait on the Markdown child is unmeasured"
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m88tv745atsmky56h05dnn0f
hold: null
hold_until: null
created_at: 2026-11-25T07:50:32.542Z
updated_at: 2026-11-25T07:51:53.863Z
started_at: 2026-11-25T07:51:53.855Z
---
guided_review.py:1077-1080 awaits up to two renders in the shared child (markdown_projection_worker.py:225-236), cold start up to _START_WAIT_S; measure cold and warm and record beside _rendered_note. Severity: Low. PR #822, review A: https://github.com/jlevy/metabrowser/pull/822#pullrequestreview-6053614872
