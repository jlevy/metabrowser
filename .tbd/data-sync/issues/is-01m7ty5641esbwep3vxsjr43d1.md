---
type: is
id: is-01m7ty5641esbwep3vxsjr43d1
title: "Event log: browser reports of slow and never-completed waits, and a link from the refresh failure line"
kind: feature
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-19-structured-event-log.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7ts09te3ty0ca6tbbsybgrj
hold: null
hold_until: null
created_at: 2026-11-19T22:17:10.526Z
updated_at: 2026-11-20T02:08:55.330Z
started_at: 2026-11-20T00:35:23.719Z
---
Phase 1 remainder of mb-wr5e (spec: Browser Reports, and the unchecked Phase 1 items). perf.js sends a client ID header the server records as the request's client; reports a fetch slower than its threshold, a fetch still pending past it, and named waits (the pull request page's Diff summary first) to a bounded, rate-limited POST /api/event-log/client, with navigator.sendBeacon on pagehide for waits that never completed; the server writes each as a browser record. The page's failure line links to /api/event-log/failures for its cause and shows the recent count. Needs a parity row and golden for the POST route and a browserless test of the reporter against the production JS. Server side already landed: the log (#618) and cause classification with the probe and the failures route (stacked PR).

## Notes

2026-11-19: Browser side built as PR #629 (claude/event-log-browser-reports, head c49fb5c15). static/event-reports.js (an on-demand bundle, also the last script of shell-tools; not a startup script, the startup scripts are 51 bytes under their budget) tags each /api/ request with x-metabrowser-client: <page>-<n>, which the server records as the request span's client and begin() passes to child jobs and processes; /api/event-log?client=<page> matches the page and its requests. It reports to a bounded POST /api/event-log/client (event_log_reports.py: named fields, 16 KiB body, 120 reports/60 s server-wide, 30/min per page, redaction, refused by index; same-origin guard refuses Origin: null and non-JSON): fetches slower than or pending at SLOW_MS = event_log.OPEN_AFTER_MS (2 s; slowest of 545 GitHub answers measured 801 ms), frames blocked >= FREEZE_MS (500 ms), and waits (githubPull:diffSummary, githubPull:refresh, source:refresh) open at WAIT_LATE_MS (10 s; checkout._pull_job median 3.0 s, max 3.8 s, Diff summary within about 5 s, under GH_TIMEOUT_S 15 s) and their end, never_completed on leaving. Sent with fetch keepalive rather than sendBeacon, which cannot send the JSON the guard requires. Pull page: the Diff summary placeholder becomes "The summary of changes has not arrived after N s." with Details, and a failed refresh's status line has Details; the panel reads /api/event-log/failures and /api/event-log?client=<page>. Parity: route row and cli-api-event-log-client golden; interaction rows shell.event-reports, shell.event-log-details, github.pull-late-waits. Tests: test_event_log_reports, test_event_reports_session (stand-in stuck checkout._pull_job: Details show it still running and the wait never_completed), the mount session's eventLogDetails, and test_event_log_details_chrome. Not covered by a test: the source:refresh and githubPull:refresh waits at their late threshold.
