---
type: is
id: is-01m76cd1gt43frv3avt96fwqhh
title: Reap servers orphaned by a crashed app at the next launch
kind: task
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
  - type: blocks
    target: is-01m76h3hdcp0ek254274recmn5
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T22:42:04.953Z
updated_at: 2026-11-12T01:48:49.867Z
started_at: 2026-11-12T00:37:52.890Z
closed_at: 2026-11-12T01:48:49.866Z
close_reason: "Done on claude/v1-robustness (3e39a21e): one owner-only records file per app process in the variant's Application Support/servers folder (pid, group, kernel start time, folder), written atomically; at launch OrphanReaper signals only groups whose leader still matches the recorded start time and group, and never a live copy's servers. Lifecycle tests with injected process factories and a fake process table, plus live tests. Pushed at 8f45a32e."
resolution: null
duplicate_of: null
---
Until host mode's stdin-EOF exit (mb-qzny) lands, a crashed or force-quit app leaves its servers running. Record each server's pid, process-group id, and start time in an owner-only state file under the app's support directory; at launch, signal only groups whose leader still matches the recorded start time (guarding pid reuse), then remove the file. Lifecycle tests with injected process factories.
