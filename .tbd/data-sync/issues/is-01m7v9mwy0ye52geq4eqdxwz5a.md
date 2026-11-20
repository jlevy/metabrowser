---
type: is
id: is-01m7v9mwy0ye52geq4eqdxwz5a
title: Check whether the PR catalog's own file handles cancel SQLite's POSIX locks
kind: bug
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
labels: []
dependencies: []
parent_id: is-01m7tv7gz4yk6tygqfexgtw0s2
created_at: 2026-11-20T01:37:59.743Z
updated_at: 2026-11-20T17:08:13.004Z
---
Review B of jlevy/metabrowser#617 (B1) reproduced that a file handle opened and closed in the same process on a SQLite database or its -shm cancels every POSIX lock SQLite holds on that file (fcntl locks are per process, released on any close). src/metabrowser/builtin_plugins/github/pull_catalog.py _admit and _database open and close the catalog and its sidecars with their own handles while connections may be live. Not verified whether it bites there: reproduce with a concurrent reader/writer in the server process; if it does, hold one handle per file for the process lifetime or move header checks to before any connection exists. Review: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5986230518
