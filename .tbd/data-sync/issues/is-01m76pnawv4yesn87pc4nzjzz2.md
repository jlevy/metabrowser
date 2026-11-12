---
type: is
id: is-01m76pnawv4yesn87pc4nzjzz2
title: "PR #359 A1: restore trusts saved roots as canonical and can start protected folders in the background"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76pmzm35hysy66g7kva9k09
hold: null
hold_until: null
created_at: 2026-11-12T01:41:22.458Z
updated_at: 2026-11-12T01:53:55.881Z
started_at: 2026-11-12T01:41:32.098Z
closed_at: 2026-11-12T01:53:55.880Z
close_reason: "Fixed in f6623bd5: RootAdmission re-resolves saved roots with lstat/readlink, stops before protected locations, refuses non-canonical spellings; aliases share one root. RootAdmissionTests, SavedSessionTests. Reply on #359."
resolution: null
duplicate_of: null
---
High. apps/macos/Sources/Metabrowser/FolderWindows.swift:213, apps/macos/Sources/ShellCore/Folders/SavedSession.swift:26. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5867702050. Same fix as B1 and C1.
