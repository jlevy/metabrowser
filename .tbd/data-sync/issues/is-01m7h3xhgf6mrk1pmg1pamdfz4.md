---
type: is
id: is-01m7h3xhgf6mrk1pmg1pamdfz4
title: Sweep MAX_LISTED_PATCH_BYTES (256 KiB, 1 MiB, 2 MiB) in H116's timed round and record it beside the constant
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-performance-campaigns.md
labels: []
dependencies: []
parent_id: is-01m7ezsky2ycgynzw5v3kct8jv
created_at: 2026-11-16T02:45:27.182Z
updated_at: 2026-11-16T02:45:27.182Z
---
From review B of PR #449 (B3, https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914053530). The bound trades a process start saved (about 17 ms) against what a stopped run prints and throws away (about 2 ms at 256 KiB, at about 130 MB/s) and the patch each request holds. By those untimed figures break-even is near 2 MiB and 1 MiB would take this repository's 90th percentile commit (817 KB). 256 KiB is a conservative pick, not a measured optimum. Waits on exp-096 (H116's timed round): sweep 256 KiB, 1 MiB and 2 MiB with the first-page and file= asks of commits of at least 1,000 sections, record Python CPU per request beside client time, and write the result into the MAX_LISTED_PATCH_BYTES docstring in src/metabrowser/diff/adapters/git.py.
