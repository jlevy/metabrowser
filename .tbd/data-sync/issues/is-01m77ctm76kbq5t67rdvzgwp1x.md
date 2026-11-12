---
type: is
id: is-01m77ctm76kbq5t67rdvzgwp1x
title: Overlapping stop notices leave stderr's blocking mode as found (#366 review B3)
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T08:08:44.517Z
updated_at: 2026-11-12T08:36:41.381Z
started_at: 2026-11-12T08:08:57.207Z
closed_at: 2026-11-12T08:36:41.380Z
close_reason: Fixed in 3190f735 on claude/cli-exit-on-eof (#366 review B3).
resolution: null
duplicate_of: null
---
Review B on #366, B3: nested or concurrent stop notices could leave the shared stderr open file nonblocking, or restore it before another notice's write.
