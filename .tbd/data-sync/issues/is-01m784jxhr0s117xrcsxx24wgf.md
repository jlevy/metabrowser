---
type: is
id: is-01m784jxhr0s117xrcsxx24wgf
title: Measure an idle Markdown worker's memory before keeping it 60 s
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T15:03:57.751Z
updated_at: 2026-11-12T15:03:57.751Z
---
Deferred from review B (B5, remainder) on jlevy/metabrowser#368. MARKDOWN_WORKER_IDLE_MS keeps the Markdown worker 60 s after leaving Markdown; its idle memory cost is not recorded. Measure an idle worker's memory in Chrome and WKWebView and record it beside the constant (AGENTS.md: measure before bounding); shorten the idle time if the cost says so.
