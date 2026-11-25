---
type: is
id: is-01m887z03v4nr8z5tqjeemx2xa
title: pytest removes a passing test's very large transient output
kind: task
status: closed
priority: 1
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/819
    at: 2026-11-25T03:27:28.280Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
hold: null
hold_until: null
created_at: 2026-11-25T02:18:41.143Z
updated_at: 2026-11-25T04:50:46.402Z
started_at: 2026-11-25T02:23:29.556Z
closed_at: 2026-11-25T04:50:46.400Z
close_reason: "Merged in #819 (c092894f1): a test's tmp_path is emptied after it passes (kept when any phase fails or errors), a passing session's basetemp is removed, dead sessions' locks are released so pytest prunes them, and test Chrome runs with --disable-default-apps so it leaves no CRX copies. Follow-ups: mb-y2pu, mb-v1j7."
resolution: null
duplicate_of: null
---
On 2026-11-24 the disk filled (814 MiB, then 0 free on a 460 GiB volume): pytest's basetemp held 7.2 GiB across 66 runs, single runs up to 1.8 GiB and 137k files, and runs two days old had not been pruned though pytest keeps three by default. With the disk full, metab's 1 GB cache reserve failed the pin goldens and the harness could not start commands. The owner asked: very large objects that are regenerated anyway are cleaned up after a test passes; small to moderate things that save time may be kept. Find which fixtures and tests write the large trees (mirrors, clones, stores, builds), remove them when the test passes (keep a failing test's output for debugging), make sure stale runs are pruned under parallel and concurrent runs, and pin it with a check.
