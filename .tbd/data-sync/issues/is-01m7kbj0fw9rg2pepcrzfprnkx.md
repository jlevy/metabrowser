---
type: is
id: is-01m7kbj0fw9rg2pepcrzfprnkx
title: "PR #489 A3: the hover card Chrome check asserts no weight for words or marks"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k4rbwpzbrxkf1686cpsmrm
hold: null
hold_until: null
created_at: 2026-11-16T23:37:26.779Z
updated_at: 2026-11-16T23:46:40.906Z
started_at: 2026-11-16T23:37:35.565Z
closed_at: 2026-11-16T23:46:40.905Z
close_reason: "Fixed in 1648d2b76 (A3): words and marks weight assertions; a bolding control fails it."
resolution: null
duplicate_of: null
---
Low. tests/dom/git-commit-summary-chrome.mjs:412, :416, :643-647, :683-693; docs/design-system.md:548-552. Assert line weight 400 and each mark at the line weight. Review: https://github.com/jlevy/metabrowser/pull/489#pullrequestreview-5929864311
