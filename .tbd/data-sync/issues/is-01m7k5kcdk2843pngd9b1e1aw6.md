---
type: is
id: is-01m7k5kcdk2843pngd9b1e1aw6
title: "PR #485 A4: The owner steps and the doctor are in the wrong order"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:20.306Z
updated_at: 2026-11-16T22:09:54.655Z
started_at: 2026-11-16T21:53:37.264Z
closed_at: 2026-11-16T22:09:54.654Z
close_reason: "Fixed in 83ef69fc3: mb-qu6j lands first and alone, runs before O1-O3 and again after (Rollout 1, testing row); one release order in Release Flow and O7: approve RELEASE_COMMIT and create its tag, go-ahead, O8 on the draft's download, approve SHA-256 and notes, publish."
resolution: null
duplicate_of: null
---
Medium. PLAN:515, :501, :503, :416-420, :323-325; docs/publishing.md:15-18. The rollout has the owner do O1-O3 before the doctor lands; O7 publishes before O8 opens the download; commit approval comes after the notarization go-ahead. Fix: land mb-qu6j alone first, run it and record its report, do O1-O3 as it directs, rerun it; release order: approve RELEASE_COMMIT and create its tag, notarization go-ahead, O8 on the draft's download, approve the SHA-256 and notes, publish. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
