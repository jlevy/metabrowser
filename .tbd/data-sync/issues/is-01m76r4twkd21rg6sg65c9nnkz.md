---
type: is
id: is-01m76r4twkd21rg6sg65c9nnkz
title: "PR #359 D1: non-symlink filesystem aliases bypass protected-root admission"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76r4r0pna9p2h3kncd2jp4q
hold: null
hold_until: null
created_at: 2026-11-12T02:07:18.925Z
updated_at: 2026-11-12T03:05:30.836Z
started_at: 2026-11-12T02:58:03.788Z
closed_at: 2026-11-12T03:05:30.834Z
close_reason: "Fixed in 353d3f5e: case-insensitive, Data-volume-aware protected locations; F_GETPATH identity. RootAdmissionTests, ProtectedLocationsTests. Reply issuecomment-6813151545."
resolution: null
duplicate_of: null
---
High. apps/macos/Sources/ShellCore/Folders/RootAdmission.swift:72, ProtectedLocations.swift:33. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5867869514.
