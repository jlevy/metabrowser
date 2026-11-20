---
type: is
id: is-01m7jfjn3jmmg4ax4kr29abqpg
title: "Group by session: fail loudly when a load case never settles (#466 review C2)"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys3bp2ndx4v4m26exf0hz
created_at: 2026-11-16T15:28:27.761Z
updated_at: 2026-11-20T17:09:13.101Z
---
Review C on #466 (C2): tests/dom/files-group-by-session.js exits 0 with empty output when a createGroupedLoads case never resolves; set process.exitCode = 1 before sessions() and clear it in finish, or name the hung case in a beforeExit handler.
