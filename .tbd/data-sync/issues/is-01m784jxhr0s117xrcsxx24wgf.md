---
type: is
id: is-01m784jxhr0s117xrcsxx24wgf
title: Measure an idle Markdown worker's memory before keeping it 60 s
kind: task
status: open
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774r5n7h5t75ydr0b6m5z00
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T15:03:57.751Z
updated_at: 2026-11-15T07:26:49.128Z
---
Deferred from review B (B5, remainder) on #368. H90's kept Markdown worker (MARKDOWN_WORKER_IDLE_MS, 60 s, markdown-worker-client.js at 6b876c54) keeps the worker after the reader leaves Markdown, and its idle memory is not recorded. The constant is not on main: #368 took H90 out (bd971661), and mb-mbd3 holds its re-test. Before H90 lands, measure an idle worker's memory in Chrome and WKWebView and record it beside the constant (AGENTS.md: measure before bounding); shorten the idle time if the cost says so.

## Notes

2026-11-15: H90's re-test is closed (mb-mbd3), so this no longer gates it. It still matters for H113's fallback: documents with wiki syntax keep the worker path, and keeping that worker alive between views needs this memory reading first. Lane W for the WebKit half.
