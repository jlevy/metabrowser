---
type: is
id: is-01m7ktd3xgb48sp0xtvfje8xry
title: "PR #494 review A1: rendered Markdown diff draws KPress's own palette; give its article the host token contract"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7ksbsx0kcg5rk05fy23nxc5
hold: null
hold_until: null
created_at: 2026-11-17T03:56:55.088Z
updated_at: 2026-11-17T03:57:10.374Z
started_at: 2026-11-17T03:57:10.374Z
---
Review A (GitHub review 5932482622) finding A1, Medium. builtin_plugins/diff/diff-markdown.js:624 creates article.kpress.kpress-inert.diff-markdown outside .metabrowser-kpress-host, so the color and radius token bridges in static/styles.css (~4449, ~4475) never reach it. With KPress 0.3.8 its blockquote gains a bar and muted text in KPress's palette and inline code turns square with KPress's border color. CHANGELOG.md:13-14 says these look the same as before. Coordinator decision: give the diff article the same token contract the document gets, measure main document / main diff / fixed diff in light and dark, and make the CHANGELOG say exactly what changes in the diff view.
