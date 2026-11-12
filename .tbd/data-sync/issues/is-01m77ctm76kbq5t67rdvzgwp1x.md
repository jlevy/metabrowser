---
type: is
id: is-01m77ctm76kbq5t67rdvzgwp1x
title: Overlapping stop notices leave stderr's blocking mode as found (#366 review B3)
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T08:08:44.517Z
updated_at: 2026-11-12T08:08:57.208Z
started_at: 2026-11-12T08:08:57.207Z
---
Review B on #366, B3: nested or concurrent stop notices could leave the shared stderr open file nonblocking, or restore it before another notice's write.
