---
type: is
id: is-01m88dmctv73eyhbsz6h8jfm4d
title: "PR #811 A11: blocks= and view= are silently ignored for YAML and JSON"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m88dfdf96exb192c9gb46hfz
hold: null
hold_until: null
created_at: 2026-11-25T03:57:45.176Z
updated_at: 2026-11-25T03:59:43.499Z
started_at: 2026-11-25T03:59:43.498Z
---
Low. pull_rendered_diff.py:597-598 answers the whole tree with 200 for blocks= on a non-Markdown file; answer 400 invalid_rendered_diff and pin it in cli-github-pull-rendered-views.txt. Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
