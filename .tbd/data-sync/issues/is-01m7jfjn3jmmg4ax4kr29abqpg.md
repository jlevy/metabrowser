---
type: is
id: is-01m7jfjn3jmmg4ax4kr29abqpg
title: "Group by session: fail loudly when a load case never settles (#466 review C2)"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T15:28:27.761Z
updated_at: 2026-11-16T15:28:27.761Z
---
Review C on #466 (C2): tests/dom/files-group-by-session.js exits 0 with empty output when a createGroupedLoads case never resolves; set process.exitCode = 1 before sessions() and clear it in finish, or name the hung case in a beforeExit handler.
