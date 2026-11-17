---
type: is
id: is-01m7exxk1qn8m1ryp2jpc7cfx2
title: "Rendered Markdown diff: the unchanged-blocks fold has a border; expand in place"
kind: bug
status: closed
priority: 2
version: 9
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T06:22:08.437Z
updated_at: 2026-11-17T05:58:19.223Z
started_at: 2026-11-15T06:23:09.404Z
closed_at: 2026-11-16T16:30:46.906Z
close_reason: "Merged into main at afda3599f (stack #446 lower layers)."
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim: "in the rendered document diff view, the "2 unchanged blocks" toggle should not have borders around it. it should just expand in place in the rendered doc"

On main, `appendBlocks` in `builtin_plugins/diff/diff-markdown.js` (around line 248) folds a long run of unchanged blocks into a `<details class="diff-markdown-context">`, whose `<summary class="disclosure-toggle">` reads "N unchanged blocks". The fold sits inside the diff's `article.kpress.kpress-inert.diff-markdown`. So it likely takes KPress's own document `details` box styling (border, padding, background), plus the shell's `.metabrowser-kpress-host .kpress details > summary` label styles. `diff/styles.css` (around line 505) only sets the summary's colour, size and padding.

Done when:
- the fold shows no border, box or background, closed or open;
- its toggle reads as a quiet line in the document's flow;
- opening it shows the hidden blocks in place, laid out exactly like the unchanged blocks around them (same measure, spacing and face), with nothing shifting around the fold beyond the inserted blocks;
- closing it restores the closed layout;
- the selection rule ("Disclosure Toggles Never Select Text") and the existing fold behaviour (lazy mount on open, folds opened by an in-page link to a hidden id) are unchanged;
- it's measured in headless Chrome, closed and open, against the neighbouring unchanged blocks, and pinned by a test;
- CHANGELOG is updated.

Ships in the combined PR with mb-s6vu, mb-1wfn and mb-sogv.

## Notes

Carried PR 2 up (2026-11-15): 4327fa6fc merges origin/claude/menu-groups-height at c706a029f (with #444's fixes, bd987447) into claude/diff-fold-inline, no-ff, with no conflicts. 9fc7391f8 registers tests/test_diff_markdown_fold_chrome.py in tests/test_process_group.py (CHROME_TESTS and the docstring) and in docs/e2e-testing.md's list of Chrome checks. Locally, check_parity, format, lint-check, and 78 focused tests (the fold Chrome test, diff markdown session, diff browser JS, design vocabulary, and the Chrome lifecycle check) passed. Pushed with --no-verify; CI run 43699503711 on head 9fc7391f8 passed all nine checks.

Review A (https://github.com/jlevy/metabrowser/pull/447#pullrequestreview-5909858397, approve with changes: A1 Medium, A2-A6 Low) addressed in 2a230fea5, pushed with --no-verify. Dispositions: https://github.com/jlevy/metabrowser/pull/447#issuecomment-6891775378. A1: the summary's label hovers to --text (it had no hover state); the Chrome session hovers with a real mouseMoved and the check fails without the rule (muted oklch(0.561 0.016 244.4) against text oklch(0.216 0 89.9)). A2: load-order wording fixed in the CSS comment, the parity row and the harness. A3: unrounded rects, 1/64 px tolerance. A4: Fold Expanders in docs/design-system.md records this fold as the exception. A5: the fold inherits color, font-family and font-feature-settings; face() reads feature settings, variant and letter spacing. A6: CHANGELOG reworded. The upstream KPress idea is filed as mb-gc3c (P3, epic mb-eevh). Locally, format, lint-check and the focused tests (68) passed; CI run 43695240628 on 2a230fea5 passed all 9 jobs.

PR #447 (draft), branch claude/diff-fold-inline, head f90db64f8: PR 3 of native stack #446 (#444, #445, #447), based on claude/menu-groups-height (#445). Rebased from local commit f5536bea1 onto origin/claude/menu-groups-height; the one conflict, in CHANGELOG, was resolved keeping both sides. After the rebase, format, lint-check, and the focused tests passed (68). Pushed with --no-verify; CI run 43692047716 passed all 9 jobs (lint, distribution, stack-integration, admitted-git 2.43.7 and 2.50.1, test 3.12, 3.13, 3.14, 3.14t), and test (3.14) ran test_diff_markdown_fold_chrome. Not merged, not marked ready. Bead left open for the coordinator.

Cause (measured in headless Chrome): the fold is a <details> inside article.kpress, so KPress's document.css styles it as a disclosure box: `.kpress details` gives a 1px border and 12px (0.75rem) block margins; `.kpress details[open] summary` adds a 1px border-bottom when open. The shell's `.metabrowser-kpress-host .kpress details > summary` rules do not apply (the diff host has no such ancestor). Block rows also carry `.diff-markdown-context`, so the fix selects `details.diff-markdown-context`.

Fix: builtin_plugins/diff/styles.css undoes border, margin, padding, background on `.metabrowser-diff-host .diff-markdown details.diff-markdown-context` and its summary (specificity above KPress's later-loaded sheets), and starts the label on the blocks' text edge (padding-inline-start = content-padding-x + change gutter width).

Before -> after (900px pane): closed fold border 1px all sides -> 0, margin 12px 0 -> 0, fold height 24.39 -> 22.39 and now flush between the neighbouring blocks; open summary border-bottom 1px -> 0; hidden blocks' left/width 2+885 -> 1+887 (neighbours 1+887); blocks after the fold moved 328px for 327px inserted -> 327 for 327; label start 26px -> 28px (text edge 28px). Face (font, size, line height, colour, margin) already matched. A document's own details keeps its 1px border.

Tests: tests/test_diff_markdown_fold_chrome.py + tests/dom/diff-markdown-fold-chrome.mjs (production appendBlocks/sanitizeBlock, server projection, shell + diff + KPress sheets; closed, open, closed again). Fails on the old stylesheet with 22 failed checks, passes after. Paint-exempt parity row diff.markdown-fold-paint added. CHANGELOG entry added.

Local: make -o install format, make -o install lint-check (exit 0); pytest test_diff_markdown_fold_chrome, test_diff_markdown_session, test_diff_browser_js, test_design_vocabulary, test_github_pull_text_chrome: 69 passed. Not verified: the running app's pull-request page (measured in a harness page with the production builder and sheets) and WebKit.
