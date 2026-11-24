---
type: is
id: is-01m87ccajvpvb9d2q4e8d11rk4
title: "PR #766 B1: a comment the sanitizer ends early is raw HTML on a thread, at A1's cost"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8577az40f83ecdxrw97hmth
hold: null
hold_until: null
created_at: 2026-11-24T18:16:37.714Z
updated_at: 2026-11-24T18:16:45.491Z
started_at: 2026-11-24T18:16:45.488Z
---
High finding B1 of review B (round 2) on PR #766 (https://github.com/jlevy/metabrowser/pull/766#pullrequestreview-6044735853). At src/metabrowser/diff/markdown_projection.py:139 (_COMMENT), :853-861 (_is_comment, _is_raw), :2224-2230 (the thread's refusal). _COMMENT matched <!-- x --!>...--> and <!--> ... --> as one comment, as MarkdownIt does, where nh3's HTML5 parser ends the comment at --!> or <!--> and builds the rest, so a thread sanitized A1's payload (12 KB: 2.1 s, 190 MB; 24 KB: 7.7 s, 554 MB). The base has the same hole.
