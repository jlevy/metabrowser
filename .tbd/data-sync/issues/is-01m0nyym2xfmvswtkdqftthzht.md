---
type: is
id: is-01m0nyym2xfmvswtkdqftthzht
title: "H46: bulk-attribute syscalls for the verification sweep"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T00:04:59.100Z
updated_at: 2026-11-14T18:42:04.248Z
---
Load-time hypothesis H46 (plan-2026-08-21-load-time-performance.md, Hypotheses). Bulk-attribute syscalls cut the verification sweep a persisted index depends on: getattrlistbulk on macOS, io_uring statx on Linux, and on Windows the USN journal as a change feed. Metric: verify-sweep duration on an unchanged 241,000-file tree. Only matters once H21 (mb-omhf) exists.
