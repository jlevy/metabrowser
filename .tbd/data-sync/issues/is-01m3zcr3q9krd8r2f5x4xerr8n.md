---
type: is
id: is-01m3zcr3q9krd8r2f5x4xerr8n
title: A tooltip whose tree row is re-rendered during its delay is never hidden
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-02T22:46:21.160Z
updated_at: 2026-10-02T22:46:21.160Z
---
Found by the browser differential; identical on 0.11.0 and the stack. If the hovered row is replaced during the 300 ms tooltip delay, the tooltip then shows at the top-left corner and stays until another hover. Hide or cancel a pending tooltip when its anchor leaves the document.
