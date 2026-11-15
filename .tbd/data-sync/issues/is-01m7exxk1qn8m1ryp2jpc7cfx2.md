---
type: is
id: is-01m7exxk1qn8m1ryp2jpc7cfx2
title: "Rendered Markdown diff: the unchanged-blocks fold has a border; expand in place"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T06:22:08.437Z
updated_at: 2026-11-15T06:22:08.437Z
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
