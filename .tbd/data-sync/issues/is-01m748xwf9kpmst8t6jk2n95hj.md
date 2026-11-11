---
type: is
id: is-01m748xwf9kpmst8t6jk2n95hj
title: Page follows navigate events and reloads once on a new boot id
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:53.672Z
updated_at: 2026-11-11T22:51:49.912Z
---
Phase 3. The page navigates on a navigate event, reloads once when the boot id changes, and refuses a root mismatch instead of silently reattaching. A browserless golden session against the production JavaScript.

## Notes

2026-11-11, from review C on jlevy/metabrowser#352 (fixed in 3669a358), superseding the earlier credential notes: the event stream may move from EventSource to a streamed fetch carrying the Authorization header; depends on mb-qzny's event-stream gate.
