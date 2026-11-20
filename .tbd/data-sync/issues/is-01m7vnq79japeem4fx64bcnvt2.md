---
type: is
id: is-01m7vnq79japeem4fx64bcnvt2
title: "Main red: source-freshness golden keeps a stale pin on /api/event-logs after #632"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T05:08:58.794Z
updated_at: 2026-11-20T05:25:24.294Z
started_at: 2026-11-20T05:09:02.913Z
closed_at: 2026-11-20T05:25:24.284Z
close_reason: "Duplicate of mb-4yso: #631 re-recorded the same golden line and main is green at ccd4f771b."
resolution: null
duplicate_of: null
---
Main run 44676764477 (f61159ade) fails tests/golden/cli-ui-source-freshness.tryscript.md. 71e2d4789 added an /api/event-logs request to the guard's sent list with pin 42382ea; #632 regenerated the fixture mirror (page pin 66f65bf) and updated the other lines concurrently. The guard stamps the page pin, so the expected value is 66f65bf. Fix: re-record that line.
