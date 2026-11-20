---
type: is
id: is-01m7ts09te3ty0ca6tbbsybgrj
title: Structured JSON event log with latency for every request and background job, browsable in Metabrowser
kind: feature
status: closed
priority: 1
version: 10
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/618
    at: 2026-11-20T17:02:19.529Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/620
    at: 2026-11-20T17:02:19.538Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
child_order_hints:
  - is-01m7ty5641esbwep3vxsjr43d1
  - is-01m7ty57a9b1d4gy8xcrhek4xq
hold: null
hold_until: null
created_at: 2026-11-19T20:47:07.583Z
updated_at: 2026-11-20T17:02:19.538Z
started_at: 2026-11-19T22:16:19.211Z
closed_at: 2026-11-20T00:32:07.750Z
close_reason: "Phase 1 server side landed: #618 (f527f0801) JSONL event log + /api/event-log; #620 (1d85c491c) cause-first GitHub failure messages, network probe, /api/event-log/failures. Browser beacon and page link: mb-9zp5; in-app log UI: mb-4rr7."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 7a959ae7-521e-4d9b-a46a-7c3f14deb025
    linked_at: 2026-11-20T16:52:58.156Z
---
Owner, 2026-11-19, verbatim: "also I'm seeing cases where data like the PR diff summary are not loading after many seconds, is latency like this captured in our logs correctl so we can debug and identify when it happens always" and "that's another important requirement, you can file a bead for it and make sure we have a new subagent working on that too. the goal would be to have a clean json log that we can browse in metabrowser itself in different ways, wiht a full ui based on the logs of metabrowser, but initially it's okay if it's an internal log to facilitate debugging. itshould be both." Today (docs/realtime-debugging.md): Server-Timing headers; a stderr text warning for requests slower than METABROWSER_SLOW_SERVER_MS; METABROWSER_REQUEST_LOG=verbose; browser perf.js console messages. Background work the page waits on (GitHub fetches, PR diff summaries) is not timed as a request.

## Notes

2026-11-19: Phase 1 server side in a native stack (#621): #618 structured event log (requests, jobs, gh/git spans, open/abandoned records, /api/event-log; CI green) and #620 (stacked) cause classification shared by gh and git (network_cause.py), connectivity probe with per-address results and an outside control, cause-led messages with the recent count, /api/event-log/failures and a cause filter. Spec: docs/project/specs/active/plan-2026-11-19-structured-event-log.md. Root cause of the owner's frequent 'gh did not answer within 15 s' on 2026-11-19: DNS sometimes answers api.github.com with an Azure-hosted address (e.g. 172.182.252.137, 20.172.24.160) this network cannot TCP-connect to; the live message now reads 'Couldn't connect to GitHub (api.github.com at 172.182.252.137): the connection timed out after 3 s; other sites are reachable; gh gave up after 10 s.' GH_TIMEOUT_S stays at 15 s. Remaining: browser reports and the page link (mb-9zp5), Phase 2 UI (mb-4rr7).

2026-11-19 (later): senior review A folded on both PRs. #618 at d06d7893a (A1-A9 and both nits: logging never raises, prune keeps live servers' segments, jobs begin on first step, four more jobs wrapped, the macOS app passes METABROWSER_STATE_DIR/XDG_STATE_HOME/METABROWSER_EVENT_LOG, write retry with backoff, compound secret names, ASCII-digit filters, failure noted before the stamp). #620 merged #618 (no rebase) and is at 8b0f6da3b (A1-A10: "error connecting to" is dns_failed; a reachable probe names failed and recently failed addresses and says DNS answers vary; control host only on macOS and never through a proxy, per the coordinator's decision recorded in the plan; HTTPS_PROXY less NO_PROXY; probe best effort; one deadline; precedence fixes; GitHub-only counts; messages now start "GitHub could not be reached because ..."). Upstream text stays in the log only, pending the owner's answer.
