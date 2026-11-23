---
type: is
id: is-01m83anmkn4q6grheww9z22vva
title: Fix pre-row Files navigation chrome layout shift in main CI
kind: bug
status: in_progress
priority: 1
version: 7
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45111133543
    at: 2026-11-23T04:31:12.047Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/731
    at: 2026-11-23T04:46:39.350Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hhr2r1bmm0ve8a6qs5nnqw
hold: null
hold_until: null
created_at: 2026-11-23T04:29:48.013Z
updated_at: 2026-11-23T05:15:33.870Z
started_at: 2026-11-23T04:31:07.504Z
---
Main CI run 45111133543 at b131131a3 shows pre-row shifts at 201/207 ms in the navigation filter bar, tab and root details. Chrome 3.12 dark 300 px CLS 0.00015 and 3.14 dark 180 px CLS 0.00011. Prior known folder age and empty-tree wrap cases have different sources. Measure the source rectangles and startup ordering, then fix the cause without relaxing layout thresholds.

## Notes

Main b131131a’s Chrome run 45111133543 recorded startup movement of the tab, folder menu, and Files filter bar. Delaying normal Source Sans reproduced it with 2 px row movement and CLS 0.00012. PR #731 now applies optional-display only to the folder header, sidebar tabs, shared toolbars and metadata, and Files list. Its first hosted attempt exposed global alias effects on PR geometry and prose; its next exact run 45115329636 passed those checks but showed a strict metadata typography mismatch in all four Python versions until all three tabs shared the policy. Final head 49e2115caa4813c568c6c7877c283d5daabd414d leaves substantive Git lists, KPress prose, and System Fonts unchanged. Exact local Chrome passed the complete Files startup/layout, shared navigation metadata, and stack heading tests (3 passed), and the deterministic probe observed CLS 0 and 0 px movement when delivered after first rows. Warm Chrome confirmed Source Sans glyphs. The exact hosted red-main recovery check is 45116282538. The bead remains open through the merge and post-merge main CI.
