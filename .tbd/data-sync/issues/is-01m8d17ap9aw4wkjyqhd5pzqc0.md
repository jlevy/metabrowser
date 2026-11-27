---
type: is
id: is-01m8d17ap9aw4wkjyqhd5pzqc0
title: Prepare diff renderer assets before the first Commit or Changes click
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/904
    at: 2026-11-26T23:36:58.753Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
hold: null
hold_until: null
created_at: 2026-11-26T22:57:06.248Z
updated_at: 2026-11-27T11:22:33.158Z
started_at: 2026-11-26T22:57:49.236Z
closed_at: 2026-11-27T11:22:33.155Z
close_reason: "Completed the asset preparation experiment and retained its raw evidence in #904. Earlier requests did not improve useful paint reliably, so the candidate was discarded."
resolution: null
duplicate_of: null
---
H131. One Chrome diagnostic found nine diff plugin asset requests after the first Commit click despite warmed server history. Test the existing browser idle loader after Git discovery. Verify earlier asset coverage, exact destination, Files startup and meaningful commit paint, and record any discarded candidate.

## Notes

Exp-109 moved eight requests ahead of both first Commits clicks. Timings overlapped. Dropped the implementation because plugin loading permanently caches a rejected module import for that document. The original patch and samples are retained; PR #904 is evidence-only.
