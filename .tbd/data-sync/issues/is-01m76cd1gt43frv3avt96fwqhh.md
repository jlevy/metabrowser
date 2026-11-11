---
type: is
id: is-01m76cd1gt43frv3avt96fwqhh
title: Reap servers orphaned by a crashed app at the next launch
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T22:42:04.953Z
updated_at: 2026-11-11T22:42:06.765Z
---
Until host mode's stdin-EOF exit (mb-qzny) lands, a crashed or force-quit app leaves its servers running. Record each server's pid, process-group id, and start time in an owner-only state file under the app's support directory; at launch, signal only groups whose leader still matches the recorded start time (guarding pid reuse), then remove the file. Lifecycle tests with injected process factories.
