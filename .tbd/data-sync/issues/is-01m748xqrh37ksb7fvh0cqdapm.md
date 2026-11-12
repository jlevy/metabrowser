---
type: is
id: is-01m748xqrh37ksb7fvh0cqdapm
title: Page title shows the short name, a bullet, and Metabrowser
kind: feature
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T03:02:48.848Z
updated_at: 2026-11-12T00:22:53.558Z
started_at: 2026-11-11T03:07:29.302Z
closed_at: 2026-11-12T00:22:53.557Z
close_reason: The page title (short name, bullet, Metabrowser) merged with jlevy/metabrowser#353 at 7a02fed4.
resolution: null
duplicate_of: null
---
Phase 1. The served shell's <title> is '<short_name> • Metabrowser' (U+2022 with spaces), rendered by the server from the identity model and kept current if the subject changes (a pin's ref switch). Browser tabs and the native app then show which folder is which. Golden or test coverage for the rendered title.

## Notes

2026-11-11: In the same PR as mb-n9p6, jlevy/metabrowser#353: the shell's <title> is '<short_name> • Metabrowser' from root_identity. Close when #353 merges.
