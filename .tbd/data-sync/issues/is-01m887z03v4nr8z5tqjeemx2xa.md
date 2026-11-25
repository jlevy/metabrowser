---
type: is
id: is-01m887z03v4nr8z5tqjeemx2xa
title: pytest removes a passing test's very large transient output
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-25T02:18:41.143Z
updated_at: 2026-11-25T02:18:41.143Z
---
On 2026-11-24 the disk filled (814 MiB, then 0 free on a 460 GiB volume): pytest's basetemp held 7.2 GiB across 66 runs, single runs up to 1.8 GiB and 137k files, and runs two days old had not been pruned though pytest keeps three by default. With the disk full, metab's 1 GB cache reserve failed the pin goldens and the harness could not start commands. The owner asked: very large objects that are regenerated anyway are cleaned up after a test passes; small to moderate things that save time may be kept. Find which fixtures and tests write the large trees (mirrors, clones, stores, builds), remove them when the test passes (keep a failing test's output for debugging), make sure stale runs are pruned under parallel and concurrent runs, and pin it with a check.
