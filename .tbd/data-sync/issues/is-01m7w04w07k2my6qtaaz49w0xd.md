---
type: is
id: is-01m7w04w07k2my6qtaaz49w0xd
title: "PR #649 A1: branch conflicts with main; event-log built-in at SDK 0.7 refused after merge"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7w04vfg21q09dmkkdsmbzwp
hold: null
hold_until: null
created_at: 2026-11-20T08:11:11.751Z
updated_at: 2026-11-20T08:47:31.872Z
started_at: 2026-11-20T08:11:19.835Z
closed_at: 2026-11-20T08:47:31.872Z
close_reason: "fixed: merged origin/main e61aeee5 (bd0e89e95), event_log sdk_version 0.8 and requirements map entry, conflicts resolved; cli-plugins-requires and sibling goldens record the 12 built-ins (b956c4ad1), charts golden 70f180380; CI run 44703997703 green at 70f180380153ea5a6531e32e219e4ddf2d427883"
resolution: null
duplicate_of: null
---
High. Merge main, bump event_log sdk_version to 0.8, add requirements map entry, regenerate goldens, resolve conflicts in tests/golden/cli-doctor, cli-github-status, cli-plugins, tests/test_github_status.py. Review: https://github.com/jlevy/metabrowser/pull/649#pullrequestreview-5989412950
