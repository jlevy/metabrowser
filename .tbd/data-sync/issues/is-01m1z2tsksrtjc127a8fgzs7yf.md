---
type: is
id: is-01m1z2tsksrtjc127a8fgzs7yf
title: Load generic JSONL renderers independently of plugin discovery order
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T23:21:39.704Z
updated_at: 2026-09-08T00:02:45.366Z
closed_at: 2026-09-08T00:02:45.365Z
close_reason: Generic JSONL registers views immediately and lazily requests agent-log assets via the SDK with disposal guards. Regression failed on the old plugin and passes now; a fresh browser opens JSONL first and both Log and Raw JSON render.
resolution: null
duplicate_of: null
---
Real browser opening events.jsonl before an agent log shows This view is unavailable. unknown-jsonl/index.js reads agentLog at module load and returns before registering views, assuming eager alphabetical loading. Use ensureKindAssets plus getRegisteredView at render time, with a disposal/generation guard, and regress the first-open and cancelled-load paths.
