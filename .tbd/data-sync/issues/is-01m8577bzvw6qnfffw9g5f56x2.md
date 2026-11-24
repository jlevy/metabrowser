---
type: is
id: is-01m8577bzvw6qnfffw9g5f56x2
title: "Review PR #765 (Diff | Current chooser) with review-github-pr and address its findings"
kind: task
status: closed
priority: 2
version: 16
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/765
    at: 2026-11-23T22:48:46.607Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m84zd2x1v206rxsr1fspew62
child_order_hints:
  - is-01m85c186mdfrmndf5n8y91j2q
  - is-01m85c1brrkrcsgqwfr7pm62zz
  - is-01m85c1hbp8vzd4tckp00dja5r
  - is-01m85c1n881hx61zn3gea3yhm0
  - is-01m85c1s5ejwp81443zgh3f4r0
  - is-01m85c1w867k2qx0nrx1ca2ztj
  - is-01m85c2236p0fkxtbc39p9650q
  - is-01m85c27350t737avw90vp39rh
  - is-01m85c29empds45q6httf9shqy
  - is-01m85c2cv5y1vwj57e44qhtzps
hold: null
hold_until: null
created_at: 2026-11-23T22:08:03.577Z
updated_at: 2026-11-24T01:06:03.832Z
started_at: 2026-11-23T22:48:43.486Z
closed_at: 2026-11-24T01:06:03.831Z
close_reason: "Review A addressed: every finding has a disposition (A1-A9 fixed, A10 declined), fixes pushed at 600e6d186 with CI run 45300900369 green; reply https://github.com/jlevy/metabrowser/pull/765#issuecomment-7118746628"
resolution: null
duplicate_of: null
---

## Notes

2026-11-23: Review A (senior, round 1) published as a formal GitHub review pinned to head 07d37cf0c, base claude/rendered-diff-no-content-refusals at 7ad9df05a: https://github.com/jlevy/metabrowser/pull/765#pullrequestreview-6031120972

Verdict: changes requested. No Blocker; 1 High (process), 2 Medium, 5 Low, 2 suggestions. CI at the head is green (run 45282745193; stack-integration skipped as integration=contained).

- A1 High (process): #759, #766, #765 are not a formal GitHub stack (stacks API returns [] for all three); gh stack link them.
- A2 Medium: with a File type chosen the toolbar overflows at 380 px (Split | Unified 31 to 91 px past the toolbar's content box; 200 px with the load-failed notice); fits at 600 and 1,063 px; the base fit these states at 380 px. Reproduced in headless Chrome 152.
- A3 Medium: Diff | Current anchors on the file's top, so a reader inside a long file is moved (Docs: paragraph 150 becomes paragraph 100 on choosing Diff); holdPlace undoes Chrome's own scroll anchoring for rendered Markdown. Reproduced in Chrome.
- A4 Low: a Markdown file left empty draws a blank body in Rendered Current. Reproduced.
- A5 Low: N with focus on a layout chip drops focus to body. Reproduced.
- A6 Low: a hunk's heading in Current can be a removed line (Git takes it from the old file). Git side reproduced; the draw is read from code.
- A7 Low: docs/project/README.md's index entry still describes the per-bar chooser.
- A8 Low: docs/browsing-history.md does not mention the chooser on a commit's page.
- A9, A10: suggestions (reserved row for a deleted held file; the chooser's x position differs by 107 px between Changes and Docs).

Checked and benign: no removed content drawn in Current (Rendered Markdown, structured, Source); defaults and preferences per surface; N attached once, retargeted, detached; the merge of #766 is the automatic merge (git merge-tree gives the committed tree).

Measurement scripts and raw JSON are in the review worktree's gitignored attic/review765/ (toolbar-widths.mjs, current-behavior.mjs, anchoring-control.mjs, disabled-hover.mjs); they are transient and are rerun with CHROME_BIN, CHROME_PROFILES, KPRESS_STATIC and REVIEW_INPUT set as each file's header says.

Not done here: no findings addressed, bead left in_progress for address-pr-review.

2026-11-23: Review A addressed (address-pr-review). Fix commits: c20c24659 (A4), 9d2d92730 (A7, A8), 462859300 (A2, A3, A5, A6, A9); the merge of #766's head 4bc0c18b2 is 600e6d186 (one comment conflict in diff-structured.js, both sides kept). Head 600e6d186740a134e9ef294f8ccb8559f6b78812, CI run 45300900369. Disposition reply: https://github.com/jlevy/metabrowser/pull/765#issuecomment-7118746628

- A1 fixed (process, no commit): the coordinator linked native stack 770 (#759, #766, #765).
- A2 fixed: the choosers are one group (.diff-toolbar-end) and the toolbar wraps; tests/test_diff_current_chrome.py mounts the production File type control in five states at 1,063 to 320 px.
- A3 fixed: a choice keeps the row at the pane's top (anchorRow, placeOfTopRow, holdPlace, settlePlace); Chrome round trips in a long code file (Unified, Split) and a long rendered document (Changes, Docs) hold within 1 px.
- A4 fixed: an emptied rendered file shows its Source sentence in Current.
- A5 fixed: renderLayoutControl restores focus to its chosen chip.
- A6 fixed: Current's hunk header has no heading.
- A7, A8 fixed: docs.
- A9 fixed: patchRowCounts counts a held absent file as one notice row in Current.
- A10 declined: the owner asked for right-aligned; the plan says the place is the toolbar's right end.

Also: tests/test_changed_file_rows_chrome.py's stale toolbar assertion (slow tier, which PR CI skips) fixed in f847a8928; tests/test_modified_keys.py lists settlePlace's keydown listener.
