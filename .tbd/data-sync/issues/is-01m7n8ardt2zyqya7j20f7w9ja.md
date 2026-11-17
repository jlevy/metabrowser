---
type: is
id: is-01m7n8ardt2zyqya7j20f7w9ja
title: "PR view and Pulls: hunt a performance regression against v0.12.0 and recent main"
kind: task
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
hold: null
hold_until: null
created_at: 2026-11-17T17:19:32.281Z
updated_at: 2026-11-17T17:21:36.438Z
started_at: 2026-11-17T17:21:36.436Z
---
The owner finds it a little slower since recent PRs. Benchmark the PR view against v0.12.0 and main from a few days ago, bisect a step change, and name the commit. Keep a durable, repeatable benchmark in explorations/performance-loop covering (1) route and git/gh time behind the diff summaries, cold and warm cache, and (2) time to display in a real browser (first paint of the loading box and of the summary, time to complete), back-to-back pairs per the tolerance policy.
