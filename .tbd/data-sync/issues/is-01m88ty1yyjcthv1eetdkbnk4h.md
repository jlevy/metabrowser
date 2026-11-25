---
type: is
id: is-01m88ty1yyjcthv1eetdkbnk4h
title: "PR #822 A6: deferred import of render_text breaks a cycle without meeting the documented bar"
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
created_at: 2026-11-25T07:50:13.213Z
updated_at: 2026-11-25T07:51:45.255Z
started_at: 2026-11-25T07:51:45.207Z
---
guided_review.py:973-974 imports render_text in _rendered_note to break the cycle with pull_markdown.py:31; docs/development.md:247-249, 294-298; same at :740-742. Severity: Low. PR #822, review A: https://github.com/jlevy/metabrowser/pull/822#pullrequestreview-6053614872
