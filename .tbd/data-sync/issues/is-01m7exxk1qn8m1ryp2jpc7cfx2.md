---
type: is
id: is-01m7exxk1qn8m1ryp2jpc7cfx2
title: "Rendered Markdown diff: the unchanged-blocks fold has a border; expand in place"
kind: bug
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T06:22:08.437Z
updated_at: 2026-11-15T06:42:05.193Z
started_at: 2026-11-15T06:23:09.404Z
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

Done on branch claude/diff-fold-inline, commit f5536bea1 (local; not pushed; PR 3 of the stack). Bead left open for the coordinator.

Cause (measured in headless Chrome): the fold is a <details> inside article.kpress, so KPress's document.css styles it as a disclosure box: `.kpress details` gives a 1px border and 12px (0.75rem) block margins; `.kpress details[open] summary` adds a 1px border-bottom when open. The shell's `.metabrowser-kpress-host .kpress details > summary` rules do not apply (the diff host has no such ancestor). Block rows also carry `.diff-markdown-context`, so the fix selects `details.diff-markdown-context`.

Fix: builtin_plugins/diff/styles.css undoes border, margin, padding, background on `.metabrowser-diff-host .diff-markdown details.diff-markdown-context` and its summary (specificity above KPress's later-loaded sheets), and starts the label on the blocks' text edge (padding-inline-start = content-padding-x + change gutter width).

Before -> after (900px pane): closed fold border 1px all sides -> 0, margin 12px 0 -> 0, fold height 24.39 -> 22.39 and now flush between the neighbouring blocks; open summary border-bottom 1px -> 0; hidden blocks' left/width 2+885 -> 1+887 (neighbours 1+887); blocks after the fold moved 328px for 327px inserted -> 327 for 327; label start 26px -> 28px (text edge 28px). Face (font, size, line height, colour, margin) already matched. A document's own details keeps its 1px border.

Tests: tests/test_diff_markdown_fold_chrome.py + tests/dom/diff-markdown-fold-chrome.mjs (production appendBlocks/sanitizeBlock, server projection, shell + diff + KPress sheets; closed, open, closed again). Fails on the old stylesheet with 22 failed checks, passes after. Paint-exempt parity row diff.markdown-fold-paint added. CHANGELOG entry added.

Local: make -o install format, make -o install lint-check (exit 0); pytest test_diff_markdown_fold_chrome, test_diff_markdown_session, test_diff_browser_js, test_design_vocabulary, test_github_pull_text_chrome: 69 passed. Not verified: the running app's pull-request page (measured in a harness page with the production builder and sheets) and WebKit.
