---
type: is
id: is-01m7hhr1qbg4f07e1scdq20d7n
title: "Release 0.13 owner: free about 25 GB of disk, turn off Low Power Mode, AC power, quiet host for the WebKit rerun and the app signing session"
kind: task
status: open
priority: 1
version: 4
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-16T06:47:07.242Z
updated_at: 2026-11-23T05:13:38.804Z
---

## Notes

2026-11-17 coordinator: the performance comparison runs in the cloud container, so this applies only to the Mac work (WebKit rerun mb-76nv, app signing).

2026-11-22 check (this session): the internal data volume was 98-99% full (11 GB free at 18:40Z, 4.6 GB free at 21:03Z, as other sessions wrote to it), Low Power Mode was on (pmset lowpowermode 1), and AC power was connected. Agent worktrees and temp files moved to /Volumes/spud-ext2/agent-scratch (103 GB free) for this reason.

2026-11-22 21:14 PT: internal data volume reported 16 GiB available, external build volume 53 GiB available. Machine was connected to AC and Low Power Mode remained enabled on AC. CLI release gates use hosted runners; signed-app checks need a quiet Mac.
