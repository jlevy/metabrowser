---
type: is
id: is-01m7ty57a9b1d4gy8xcrhek4xq
title: "Event log Phase 2: browse Metabrowser's own event log in Metabrowser"
kind: feature
status: closed
priority: 2
version: 14
spec_path: docs/project/specs/active/plan-2026-11-19-structured-event-log.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/633
    at: 2026-11-20T17:04:41.368Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/634
    at: 2026-11-20T17:04:41.409Z
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
updated_at: 2026-11-20T19:16:01.413Z
started_at: 2026-11-20T02:55:08.942Z
closed_at: 2026-11-20T07:25:02.836Z
close_reason: "Merged in PRs 633 and 634. Follow-ups: mb-9n0x, mb-7uqr."
resolution: null
duplicate_of: null
extensions: {}
---
Phase 2 of mb-wr5e (spec: Phase 2). A log view for the event schema beside the agent-log and JSONL views, picked for events-*.jsonl; views by latency, by kind, slowest, errors, and a timeline nesting spans under parents; a way to open the log from the app (menu command) and the shell, and from the refresh failure line; a metab equivalent and golden for each view's query (parity rule). Owner's goal, 2026-11-19: a clean JSON log browsable in Metabrowser in different ways, with a full UI based on Metabrowser's own logs.

## Notes

2026-11-19: stacked in two pull requests (native stack #635). #633 (claude/event-log-ui, head 0e4d1f341): the event-log plugin, its four routes (timeline, slowest, kinds, errors), goldens, browserless session, Chrome test, parity rows, docs; CI green. #634 (claude/event-log-open, head b88a3077b): metab --event-log, the macOS app's Help > Open Event Log (EventLogLocation, contract command and scenarios), and the command named in the pull request page's Details; CI green except the stack-integration golden cli-ui-source-freshness, which fails on main itself (PR 632's merge, run 44676764477). Not hand-checked: the menu item in a running app window. Open: the owner's review.

2026-11-19 (later): senior review A folded in one round, dispositions posted on both PRs. #633 at f8ae4c413 (merges of main at cc18fcdef and 800c6fdfa): the self-logging rule narrowed (a server whose folder is the events directory or inside it opens no log and says why: a warning, Details, metab --doctor's new event_log check; a folder that holds it, such as metab ~, logs and skips requests whose target resolves inside the directory, event_log.quiet_request); keyboard focus kept on rows and Show more; Show in timeline from Latency rows and Errors examples (timeline focus=KEY, order=newest, navigation.open now honors viewId for the shown file); linear depth and cycle checks; pid and the span's own key on failure examples; clamped numbers and a 422 naming a file that raises; chips wrap (filter bar measured in Chrome); a later-segment wording; 413, not_jsonl, traversal, symlink and eviction tests; least times from the server's edges; shared filters per file. CI at 800c6fdfa failed because the doctor's new row is listed by test_golden_app_contract and the Swift DoctorReportTests and LiveMetabTests; fixed in 7dba5c806, and check_app_contract wanted an App contract changelog entry (f8ae4c413). #634 at 8d25866a3 (merged #633 three times): Help > Open Event Log opens the log's own directory as its window's root (OpenTarget with no open roots), not recorded in Open Recent; Details name the menu item for a server the app started and the command otherwise; EventLogLocation.action and .target tested; a hand-check entry (qa-macos-app-hand-checks.md, Help > Open Event Log). Follow-ups: mb-9n0x (measure open to first row, skip the JSONL envelope for hook-backed kinds), mb-7uqr (name, client, cause chips). Not hand-checked: the Help menu in a running app. Open: CI on both heads, the owner's review.
