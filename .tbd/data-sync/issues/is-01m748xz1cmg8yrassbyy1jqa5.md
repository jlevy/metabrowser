---
type: is
id: is-01m748xz1cmg8yrassbyy1jqa5
title: Optional app-private runtime for offline, managed, or hash-pinned setups
kind: feature
status: open
priority: 4
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:56.299Z
updated_at: 2026-11-11T17:08:45.181Z
---
Phase 5, narrowed by research-2026-11-11-uv-and-macos-app-install.md: Flow 2's Install for me (uv tool install in uv's standard locations) is the default for a user without metab. This bead is the optional app-private runtime from the 2026-11-08 brief (a bundled uv plus a hash-pinned pylock.toml), built only when an offline, managed, or hash-pinned setup needs it.
