---
type: is
id: is-01m2f0fxws993378tf9qnck86f
title: "PR #114 review R1: staged document's prepare-primary waits behind outgoing document's queued transclusions in the page-wide Worker FIFO"
kind: bug
status: closed
priority: 1
version: 2
labels:
  - markdown
dependencies: []
parent_id: is-01m2f0fb55v9h6480r6cfx514k
created_at: 2026-09-14T03:48:37.400Z
updated_at: 2026-09-14T04:45:53.706Z
closed_at: 2026-09-14T04:45:53.705Z
close_reason: "Fixed in de282ce5: primary preparations dispatch from their own FIFO lane ahead of queued transclusions; released references cancel queued work before dispatch. Two-reference test fails on ae3c976a. Real-browser latency measurement remains in mb-k8os."
resolution: null
duplicate_of: null
---
PR #114 review R1 (Medium). src/metabrowser/builtin_plugins/markdown/markdown-worker-client.js:28-78, consequence in src/metabrowser/static/app.js:5898-5925 and src/metabrowser/static/view-composition.js:57-58,162. The shell awaits the staged mount's ready (which includes prepare-primary) before commit() disposes the old mount, but the shared client is one FIFO, so the new primary dispatches after the old mount's queued prepare-transclusion requests. Fix: priority lane for prepare-primary ahead of queued prepare-transclusion; disposal cancels queued requests before dispatch; two-reference test.
