---
type: is
id: is-01m77fa8zqx6w6jjfanz34bqtt
title: "Review G1 on #363: the gate's static server can serve an unlisted file through a symlink"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T08:52:14.454Z
updated_at: 2026-11-12T08:54:58.667Z
started_at: 2026-11-12T08:52:26.055Z
closed_at: 2026-11-12T08:54:58.665Z
close_reason: "Fixed in bc98a4d4 (#363): each listed file is identified at startup (O_NOFOLLOW open, real path equals listed path, same inode) and a request serves only that device and inode, opened with O_NOFOLLOW; static-server.test.mjs covers an in-root alias and file and directory swaps."
resolution: null
duplicate_of: null
---
static-server.mjs checked a listed file's real path only against its root, so a listed path that is a symlink to an unlisted file in the root was served, and a file or ancestor replaced with a symlink between realpath() and open() was followed. Identify each listed file once at startup (no symlink on its path, a plain file) and serve only that inode, opened with O_NOFOLLOW.
