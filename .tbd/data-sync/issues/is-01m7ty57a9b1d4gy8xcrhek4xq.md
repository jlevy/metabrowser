---
type: is
id: is-01m7ty57a9b1d4gy8xcrhek4xq
title: "Event log Phase 2: browse Metabrowser's own event log in Metabrowser"
kind: feature
status: in_progress
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-19-structured-event-log.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7ts09te3ty0ca6tbbsybgrj
child_order_hints:
  - is-01m7vsaw74j5kjh877686npatq
  - is-01m7vsaz137bzapm5p4jbjp04d
hold: null
hold_until: null
created_at: 2026-11-19T22:17:11.751Z
updated_at: 2026-11-20T06:12:11.424Z
started_at: 2026-11-20T02:55:08.942Z
---
Phase 2 of mb-wr5e (spec: Phase 2). A log view for the event schema beside the agent-log and JSONL views, picked for events-*.jsonl; views by latency, by kind, slowest, errors, and a timeline nesting spans under parents; a way to open the log from the app (menu command) and the shell, and from the refresh failure line; a metab equivalent and golden for each view's query (parity rule). Owner's goal, 2026-11-19: a clean JSON log browsable in Metabrowser in different ways, with a full UI based on Metabrowser's own logs.

## Notes

2026-11-19: stacked in two pull requests (native stack #635). #633 (claude/event-log-ui, head 0e4d1f341): the event-log plugin, its four routes (timeline, slowest, kinds, errors), goldens, browserless session, Chrome test, parity rows, docs; CI green. #634 (claude/event-log-open, head b88a3077b): metab --event-log, the macOS app's Help > Open Event Log (EventLogLocation, contract command and scenarios), and the command named in the pull request page's Details; CI green except the stack-integration golden cli-ui-source-freshness, which fails on main itself (PR 632's merge, run 44676764477). Not hand-checked: the menu item in a running app window. Open: the owner's review.
