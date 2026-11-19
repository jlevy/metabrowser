---
type: is
id: is-01m7tk4x6n6hgq7kadft288045
title: "Type-scale Chrome test: check the commit-ID x-height ratio in the System font set too"
kind: task
status: open
priority: 4
version: 1
labels: []
dependencies: []
created_at: 2026-11-19T19:04:47.059Z
updated_at: 2026-11-19T19:04:47.059Z
---
From #613 review A3: tests/dom/type-scale-chrome.mjs:354-376 checks .git-commit-sha's x-height against the line only in Clean Fonts; run the same check with data-app-font="system" so a change to system-ui metrics or the System stack can't leave --font-sans-ex-height (0.526) stale unnoticed.
