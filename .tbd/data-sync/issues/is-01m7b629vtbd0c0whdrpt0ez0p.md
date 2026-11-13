---
type: is
id: is-01m7b629vtbd0c0whdrpt0ez0p
title: Stack N/P stay live during the PR page's held first paint
kind: bug
status: open
priority: 4
version: 1
labels: []
dependencies: []
created_at: 2026-11-13T19:27:33.753Z
updated_at: 2026-11-13T19:27:33.753Z
---
Low, from the keymap compatibility review after #369. pull-page.js paint() sets shown = model before the first-paint hold, and currentStack() reads shown, so N, P and their reveal-strip entries are available for up to DESCRIPTION_HOLD_MS while the header (and its stack menu) still shows the loading heading; C, G and H are dead during the hold. Option: return null from currentStack() while firstPaint?.header, or document the asymmetry.
