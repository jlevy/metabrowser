---
type: is
id: is-01kzkv876kex53a3ec4364kfm5
title: "PR #22 review R11: Enter or click can open a result for the previous query"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01kzkv76p2eprd181arkqfj0we
created_at: 2026-08-09T18:06:08.594Z
updated_at: 2026-08-09T18:06:08.594Z
---
search_palette.js:373-389 and 591-593. Held rows avoid flicker but are semantically stale relative to the current combobox value: change the input while withholding the new completion, press Enter, and openFile() is called with the old path. Supersedes the earlier R2 rebuttal, which addressed DOM/array consistency rather than the query mismatch. Fix: track the query that produced the rendered rows; keep them painted but inert (aria-disabled) and suppress Enter/click until they correspond to input.value, or retain only rows that still match the new query. This is fallout from the flicker fix in 2be5d58.
