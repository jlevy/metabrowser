---
type: is
id: is-01m784mz5kd9vnjhbchmkaa6e0
title: Measure the idle helper's input pause and sampling window in WKWebView
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T15:05:04.946Z
updated_at: 2026-11-12T15:05:04.946Z
---
Deferred from review A (A1 remainder, A2) on jlevy/metabrowser#372. metabrowser.whenIdle() falls back to timers where requestIdleCallback is absent (WebKit). Its 250 ms input pause and 10 s sampling window are named constants chosen, not measured, in the app's engine, and untimed idle work has no ceiling. Register the WebKit idle timing as a hypothesis row and read it with the WKWebView probe (mb-fevz): how long idle work waits after input, whether it starves under continuous input, and whether a hidden web view ever runs it.
