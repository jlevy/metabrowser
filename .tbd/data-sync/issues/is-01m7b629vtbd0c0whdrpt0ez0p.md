---
type: is
id: is-01m7b629vtbd0c0whdrpt0ez0p
title: Stack N/P stay live during the PR page's held first paint
kind: bug
status: in_progress
priority: 4
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-13T19:27:33.753Z
updated_at: 2026-11-14T01:20:07.643Z
started_at: 2026-11-14T01:20:07.641Z
---
Low, from the keymap compatibility review after #369. pull-page.js paint() sets shown = model before the first-paint hold, and currentStack() reads shown, so N, P and their reveal-strip entries are available for up to DESCRIPTION_HOLD_MS while the header (and its stack menu) still shows the loading heading; C, G and H are dead during the hold. Option: return null from currentStack() while firstPaint?.header, or document the asymmetry.
