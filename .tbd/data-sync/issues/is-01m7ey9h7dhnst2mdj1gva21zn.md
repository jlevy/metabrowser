---
type: is
id: is-01m7ey9h7dhnst2mdj1gva21zn
title: "Unused settings and event types: INVENTORY_REFRESH_TTL_S, File*/ParserReset/Heartbeat events"
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7ey9fq9v53mp3c974mg2d89
created_at: 2026-11-15T06:28:39.788Z
updated_at: 2026-11-15T06:28:39.788Z
---
INVENTORY_REFRESH_TTL_S is never read. The File*, ParserReset, and Heartbeat event types and _EventBus.publish have no production caller. Remove or wire them.
