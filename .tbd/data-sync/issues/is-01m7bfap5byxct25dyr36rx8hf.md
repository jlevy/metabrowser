---
type: is
id: is-01m7bfap5byxct25dyr36rx8hf
title: "Markdown view: outside images still blank on re-entry in the macOS app"
kind: bug
status: in_progress
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-11-13T22:09:25.674Z
updated_at: 2026-11-14T00:49:46.098Z
---
Follow-up from #408 (mb-wzly). The fix makes re-entered Markdown images inside the served tree eager, but an image from outside the tree (a badge, for example) keeps the lazy address KPress authored at parse time. Measured in the app's WKWebView with max-age=300: 1 request and 3 blank frames per re-entry, 5 of 5; Chrome 0 / 0 (records `attic/webkit-after-ext.json` and `attic/chrome-after-ext.json` in the md-images-webkit worktree).

Likely fix: parse through a `<template>` in `place-rendered.js` and set `loading` on held images before insertion (this changes the core placement path and the mount test doubles).

Done when outside images also keep their pixels across re-entry in WebKit, measured, with a test.
