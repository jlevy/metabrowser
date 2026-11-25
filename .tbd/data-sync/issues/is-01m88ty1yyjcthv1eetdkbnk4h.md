---
type: is
id: is-01m88ty1yyjcthv1eetdkbnk4h
title: "PR #822 A6: deferred import of render_text breaks a cycle without meeting the documented bar"
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
created_at: 2026-11-25T07:50:13.213Z
updated_at: 2026-11-25T08:57:56.540Z
started_at: 2026-11-25T07:51:45.207Z
closed_at: 2026-11-25T08:57:56.516Z
close_reason: "Fixed in d067c9779: render_text moved to pull_text_render.py, cycle and deferred import gone; the pull_rendered_diff import's boundary test is mb-iqlb. PR #822 review A dispositions: https://github.com/jlevy/metabrowser/pull/822#issuecomment-7157686246"
resolution: null
duplicate_of: null
---
guided_review.py:973-974 imports render_text in _rendered_note to break the cycle with pull_markdown.py:31; docs/development.md:247-249, 294-298; same at :740-742. Severity: Low. PR #822, review A: https://github.com/jlevy/metabrowser/pull/822#pullrequestreview-6053614872
