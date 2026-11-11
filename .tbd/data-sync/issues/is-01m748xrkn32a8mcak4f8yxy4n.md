---
type: is
id: is-01m748xrkn32a8mcak4f8yxy4n
title: Keep folders warm after their windows close
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:49.716Z
updated_at: 2026-11-11T03:02:49.716Z
---
Phase 2, shell only. A server lingers after its folder's last window closes, capped by measured footprint and idle CPU, least recently shown evicted first; all stop on quit. Depends on the activity tracker fix (mb-z46o) so log-heavy folders are cheap to keep warm.
