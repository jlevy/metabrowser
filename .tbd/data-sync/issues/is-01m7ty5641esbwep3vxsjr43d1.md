---
type: is
id: is-01m7ty5641esbwep3vxsjr43d1
title: "Event log: browser reports of slow and never-completed waits, and a link from the refresh failure line"
kind: feature
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-11-19-structured-event-log.md
labels: []
dependencies: []
parent_id: is-01m7ts09te3ty0ca6tbbsybgrj
created_at: 2026-11-19T22:17:10.526Z
updated_at: 2026-11-19T22:17:10.526Z
---
Phase 1 remainder of mb-wr5e (spec: Browser Reports, and the unchecked Phase 1 items). perf.js sends a client ID header the server records as the request's client; reports a fetch slower than its threshold, a fetch still pending past it, and named waits (the pull request page's Diff summary first) to a bounded, rate-limited POST /api/event-log/client, with navigator.sendBeacon on pagehide for waits that never completed; the server writes each as a browser record. The page's failure line links to /api/event-log/failures for its cause and shows the recent count. Needs a parity row and golden for the POST route and a browserless test of the reporter against the production JS. Server side already landed: the log (#618) and cause classification with the probe and the failures route (stacked PR).
