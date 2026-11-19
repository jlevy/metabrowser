---
type: is
id: is-01m7ts09te3ty0ca6tbbsybgrj
title: Structured JSON event log with latency for every request and background job, browsable in Metabrowser
kind: feature
status: in_progress
priority: 1
version: 5
delegate: claude-code@spud10
labels: []
dependencies: []
child_order_hints:
  - is-01m7ty5641esbwep3vxsjr43d1
  - is-01m7ty57a9b1d4gy8xcrhek4xq
hold: null
hold_until: null
created_at: 2026-11-19T20:47:07.583Z
updated_at: 2026-11-19T22:24:03.019Z
started_at: 2026-11-19T22:16:19.211Z
---
Owner, 2026-11-19, verbatim: "also I'm seeing cases where data like the PR diff summary are not loading after many seconds, is latency like this captured in our logs correctl so we can debug and identify when it happens always" and "that's another important requirement, you can file a bead for it and make sure we have a new subagent working on that too. the goal would be to have a clean json log that we can browse in metabrowser itself in different ways, wiht a full ui based on the logs of metabrowser, but initially it's okay if it's an internal log to facilitate debugging. itshould be both." Today (docs/realtime-debugging.md): Server-Timing headers; a stderr text warning for requests slower than METABROWSER_SLOW_SERVER_MS; METABROWSER_REQUEST_LOG=verbose; browser perf.js console messages. Background work the page waits on (GitHub fetches, PR diff summaries) is not timed as a request.

## Notes

2026-11-19: Phase 1 server side in a native stack (#621): #618 structured event log (requests, jobs, gh/git spans, open/abandoned records, /api/event-log; CI green) and #620 (stacked) cause classification shared by gh and git (network_cause.py), connectivity probe with per-address results and an outside control, cause-led messages with the recent count, /api/event-log/failures and a cause filter. Spec: docs/project/specs/active/plan-2026-11-19-structured-event-log.md. Root cause of the owner's frequent 'gh did not answer within 15 s' on 2026-11-19: DNS sometimes answers api.github.com with an Azure-hosted address (e.g. 172.182.252.137, 20.172.24.160) this network cannot TCP-connect to; the live message now reads 'Couldn't connect to GitHub (api.github.com at 172.182.252.137): the connection timed out after 3 s; other sites are reachable; gh gave up after 10 s.' GH_TIMEOUT_S stays at 15 s. Remaining: browser reports and the page link (mb-9zp5), Phase 2 UI (mb-4rr7).
