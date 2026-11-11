---
type: is
id: is-01m76bf0syr48edst0accjg3ky
title: "PR #341 B3: the final group SIGKILL can follow the reap of the leader (pid reuse)"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76bebqayw0ze5xz60yhthtw
hold: null
hold_until: null
created_at: 2026-11-11T22:25:41.182Z
updated_at: 2026-11-11T22:54:11.966Z
started_at: 2026-11-11T22:54:11.954Z
---
High. ShellCore/Supervision/ServerProcess.swift:201 reaps in the exit handler; ServerSupervisor.swift:309 and CommandRunner.swift:65 then kill(-pid). Review B3 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036340.
