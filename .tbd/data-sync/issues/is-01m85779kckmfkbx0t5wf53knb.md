---
type: is
id: is-01m85779kckmfkbx0t5wf53knb
title: "Review PR #677 (Guided Review walkthroughs) with review-github-pr and address its findings"
kind: task
status: closed
priority: 2
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7x3g8rdhbeh7f0j0j7nz4sq
hold: null
hold_until: null
created_at: 2026-11-23T22:08:01.130Z
updated_at: 2026-11-24T00:20:59.451Z
started_at: 2026-11-23T22:32:53.975Z
closed_at: 2026-11-24T00:20:59.450Z
close_reason: "Every review B finding on PR #677 has a disposition (B15 deferred to mb-y0en, B18 and B19 declined, the rest fixed), the fixes are pushed at 59d45662 with CI green, and the reply is posted at https://github.com/jlevy/metabrowser/pull/677#issuecomment-7117903425."
resolution: null
duplicate_of: null
---

## Notes

Review B on #677 (https://github.com/jlevy/metabrowser/pull/677#pullrequestreview-6030556971) addressed on claude/guided-pr-ready.

Commits: 6e2409758 (route: B1, B2, B3 server, B4, B5, B8, B9, B10, B11, B12, B13, B16, B17), 2d435ea0e (page: B1, B3, B7, B10, B13, B14, B16, B20), e9b6e31ea (B6, real mountFilePatch test), 95ec020c4 (docs), a9d305a2a (newer-head wording, R session line), 59d456621 (merge origin/main at c7e2b5991). Pushed head 59d456621c052836a7e48dbb0b927a0d818499d1.

Dispositions: B1-B14, B16, B17, B20 fixed; B15 deferred to mb-y0en; B18, B19 declined.

B4: measured in headless Chrome 152, 2026-11-23, load near 280 (to 434): ranged steps at the excerpt budget draw in 24 ms; whole files at 1,956,140 bytes of charge 208 ms with a 91-103 ms task; new MAX_STEP_PATCH_BYTES = 1,950,000.

Tests: tests/test_guided_pr_route.py (18), tests/test_guided_pr.py (40), route golden +3 calls, UI goldens re-recorded, diff-view-behavior.js mountFilePatch block. Focused pytest after the merge: 345 passed, 1 xfailed.

The PR description's guide is re-pinned to 59d45662 on c7e2b599: 11 steps, all ready, excerpt rows match the pins.

CI at 59d45662: run 45294957195 (CI) success, run 45294957157 (macOS app) success; gh pr checks 18 pass, 1 skipping. Disposition reply for review B: https://github.com/jlevy/metabrowser/pull/677#issuecomment-7117903425 (B15 deferred to mb-y0en; B18, B19 declined; the rest fixed). PR not merged, at the user's word.
