---
type: is
id: is-01m7vsaz137bzapm5p4jbjp04d
title: "Event log Timeline: name, client, and cause chips"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-19-structured-event-log.md
labels: []
dependencies: []
parent_id: is-01m7wysap12x9d1xp4zz3m4sds
created_at: 2026-11-20T06:12:11.424Z
updated_at: 2026-11-20T17:11:40.724Z
---
From senior review A of #633 (A3, in part). The plugin's routes already take the name, client, and cause filters of /api/event-log (event_log_views.parse_filter), but the page's filter bar offers only kind, outcome, least time, and (new) order. A person who comes to the log for one page's requests (client) or one failure cause cannot narrow to it without the URL.

Do: a name filter (a text field, the substring /api/event-log's name filter takes), a client filter reached from a row's detail ("Only this page's requests"), and a cause filter reached from an Errors cause, each shared across the file's views through the per-file shared state (event-log-model.js createShared) and sent by filterParams; session and Chrome tests; parity registry (event-log.view-state). Keep the filter bar's every chip inside a 260 px pane (tests/test_event_log_view_chrome.py).
