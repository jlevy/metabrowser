---
type: is
id: is-01m7k5kkfgb40z07d073xz0yy1
title: "PR #485 A17: The translocated launch restores less state than the release identity keeps"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:27.535Z
updated_at: 2026-11-16T22:10:03.629Z
started_at: 2026-11-16T21:53:42.298Z
closed_at: 2026-11-16T22:10:03.628Z
close_reason: "Fixed in 83ef69fc3: mb-u36j unregisters each scratch copy with lsregister -u and restores the recent-documents list, beside the defaults and session.json; a VM or second account stays preferred."
resolution: null
duplicate_of: null
---
Low. PLAN:461-464; apps/macos/README.md:86, :318. Fix: unregister each scratch copy with lsregister -u and restore the recent-documents list, or require a VM or second account. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
