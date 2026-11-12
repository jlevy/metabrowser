---
type: is
id: is-01m77g4ztt8gpem1tpfv6d23z2
title: A stop always looks for groups once more after checking spawns under way (#366 review C2)
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T09:06:49.817Z
updated_at: 2026-11-12T09:27:47.129Z
started_at: 2026-11-12T09:07:31.957Z
closed_at: 2026-11-12T09:27:47.128Z
close_reason: Fixed in d018a9b1 on claude/cli-exit-on-eof (#366 review C2).
resolution: null
duplicate_of: null
---
Review C on #366, C2: the final scan ran only when the stop had waited, so a spawn that forked and registered during the first scan escaped.
