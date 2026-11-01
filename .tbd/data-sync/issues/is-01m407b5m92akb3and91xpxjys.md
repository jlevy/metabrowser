---
type: is
id: is-01m407b5m92akb3and91xpxjys
title: Resolve in-app browser file-selection QA discrepancy
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-03T06:31:08.680Z
updated_at: 2026-11-01T16:21:26.643Z
closed_at: 2026-11-01T16:21:26.642Z
close_reason: "Did not reproduce with real input on 2026-11-01: a real click on README opened README on PR #268's mirror, and 7 clicks plus ArrowDown were correct on a small fixture. Two automation hazards reproduced, a screenshot lagging the DOM and a click frame differing from DOM rects, so automation targeting is the likely cause (inferred, not proved). mb-m20f still exercises navigation."
resolution: null
duplicate_of: null
---
During candidate manual QA, selecting the visible README row through in-app browser automation repeatedly opened or retained Makefile; keyboard focused README without opening it. No console error was reported. Root overview and Makefile rendered from the new flat cache path. Determine whether this is automation targeting/stale state or a product defect before accepting file navigation. Use only the in-app browser; do not claim a confirmed product regression yet.
