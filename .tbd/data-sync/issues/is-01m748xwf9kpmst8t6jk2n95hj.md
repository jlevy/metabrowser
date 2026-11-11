---
type: is
id: is-01m748xwf9kpmst8t6jk2n95hj
title: Page follows navigate events and reloads once on a new boot id
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:53.672Z
updated_at: 2026-11-11T03:02:53.672Z
---
Phase 3. The page navigates on a navigate event, reloads once when the boot id changes, and refuses a root mismatch instead of silently reattaching. A browserless golden session against the production JavaScript.
