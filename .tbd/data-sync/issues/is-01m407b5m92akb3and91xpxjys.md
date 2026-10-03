---
type: is
id: is-01m407b5m92akb3and91xpxjys
title: Resolve in-app browser file-selection QA discrepancy
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-03T06:31:08.680Z
updated_at: 2026-10-03T06:31:08.680Z
---
During candidate manual QA, selecting the visible README row through in-app browser automation repeatedly opened or retained Makefile; keyboard focused README without opening it. No console error was reported. Root overview and Makefile rendered from the new flat cache path. Determine whether this is automation targeting/stale state or a product defect before accepting file navigation. Use only the in-app browser; do not claim a confirmed product regression yet.
