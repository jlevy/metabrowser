---
type: is
id: is-01m7ktd3xgb48sp0xtvfje8xry
title: "PR #494 review A1: rendered Markdown diff draws KPress's own palette; give its article the host token contract"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7ksbsx0kcg5rk05fy23nxc5
hold: null
hold_until: null
created_at: 2026-11-17T03:56:55.088Z
updated_at: 2026-11-17T04:19:32.273Z
started_at: 2026-11-17T03:57:10.374Z
closed_at: 2026-11-17T04:19:32.273Z
close_reason: "Fixed in 46c4db1b on #494: the color and corner token bridges key on :root .kpress, so the rendered Markdown diff draws quotes and code as the document does; measured equal to the document in headless Chrome, light and dark; fold Chrome session and a contract test pin it; CHANGELOG states the visible diff-view change (0a888335)."
resolution: null
duplicate_of: null
---
Review A (GitHub review 5932482622) finding A1, Medium. builtin_plugins/diff/diff-markdown.js:624 creates article.kpress.kpress-inert.diff-markdown outside .metabrowser-kpress-host, so the color and radius token bridges in static/styles.css (~4449, ~4475) never reach it. With KPress 0.3.8 its blockquote gains a bar and muted text in KPress's palette and inline code turns square with KPress's border color. CHANGELOG.md:13-14 says these look the same as before. Coordinator decision: give the diff article the same token contract the document gets, measure main document / main diff / fixed diff in light and dark, and make the CHANGELOG say exactly what changes in the diff view.
