---
type: is
id: is-01m7kbqxknjwbz2n4prbk2gz0s
title: "PR #485 B5: The app's tag rule has no step for the retry that Failure Handling allows"
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
created_at: 2026-11-16T23:40:40.433Z
updated_at: 2026-11-16T23:48:27.749Z
started_at: 2026-11-16T23:40:41.460Z
closed_at: 2026-11-16T23:48:27.748Z
close_reason: "Fixed in 9e7d362be: publishing.md step 2 accepts a tag already at RELEASE_COMMIT on a retry (skip step 3) and stops on any other commit; step 4 says the draft job runs it in CI; the clone rationale is now the API call taking the approved SHA itself."
resolution: null
duplicate_of: null
---
Low. docs/publishing.md:182-186, :196-201, :234-238. Step 2 requires a 404 but a retry reuses the tag; in CI the draft job runs step 4; the clone rationale is inexact. Fix: absent or, on a retry, already at RELEASE_COMMIT (skip step 3); say the draft job runs step 4 in CI; replace the clone reason with: the API call takes the approved SHA itself. Review B (follow-up, round 2) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5929906549
