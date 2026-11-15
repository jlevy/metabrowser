---
type: is
id: is-01m7dmnpft454nezmv4h7m8acy
title: "Rendered Markdown: chrome always sans, documents serif unless the sans preference is on"
kind: task
status: in_progress
priority: 2
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-14T18:21:18.188Z
updated_at: 2026-11-15T05:46:08.477Z
started_at: 2026-11-14T18:21:23.995Z
---
The user (2026-11-14): "Let's make sure we have a clear system about when we use serif and sans-serif for rendered markdown. chrome and PR descriptions etc are always sans. but document rendering is by default serif, unless we have preferences settings set to sans serif, and then they are sans serif too. for documents, when we render them in rendered view, they should use document rendering, so be serif unless sans is enabled in preferences."

The rule has two contexts:
- Chrome Markdown (PR descriptions, PR and review comments, commit message bodies, issue and bead bodies, tooltips, any Markdown inside the app's own interface) is always sans, whatever the reading-font preference says.
- Document rendering (a Markdown file, or any document, in rendered view) is serif by default and sans only when the reading-font preference (`metabrowser.proseFont`, `data-prose-font` on <html>) is set to sans.

Main already has parts of this: `html[data-prose-font="sans"]` in static/styles.css bridges `--kpress-host-font-prose`, the github plugin's styles.css forces `--kpress-host-font-prose: var(--prose-sans-font)` for PR pages, and `.git-commit-body` uses `--prose-sans-font`.

Done when every surface that renders Markdown is inventoried with its context (chrome or document) and the face it uses today; each surface follows the rule through one named mechanism (one context marker or scope, not per-surface font overrides); the rule is stated once in the design-system docs and in the views/models/routes map where a surface is registered; a browserless or golden test pins the face each context resolves to under both preference values; and any surface that broke the rule is fixed. Spacing of headings is mb-orvr's, not this bead's.

## Notes

Draft PR #438 (branch claude/markdown-font-rule), head 37063f43, CI green on every job (lint, distribution, stack-integration, admitted-git x2, test 3.12/3.13/3.14/3.14t; test_prose_faces_chrome ran and passed in all four test jobs). Commits: 5708e456 (the change); 6cae1afd (merge of origin/main 4310f5ac, #432); edfea5ce (the Chrome session lays a text out and waits two frames and the font set before reading its drawn face, and retries for up to 2 s, after test (3.13) on 6cae1afd got no platform face for the commit body in one of four combinations); 37063f43 (merge of origin/main 079a3ec0, #433 and #436; CHANGELOG kept both sides).

Mechanism: one host class, `.chrome-prose` (static/styles.css), on the element that holds a message, never on a page. It sets `font-family: var(--prose-sans-font)` and `--kpress-host-font-prose: var(--prose-sans-font)`. Carried by pull-page.js textBlock (PR description, comments, reviews, and review-thread comments, plain and rendered) and by the git-panel.js commit body. Documents keep the html[data-prose-font] path; the md-body fallback reads --kpress-font-prose. Removed: the page-wide .github-pull bridge, .github-pull-plain font-family, and .git-commit-body font-family. The rule is stated once in docs/design-system.md, "Serif Is for Documents"; docs/plugins.md tells plugin authors to use the class.

Inventory, measured in headless Chrome, clean font set, reading font serif / sans:
- Document view, transclusion, Overview README, PR "View file", PR revision snapshot page (documents): PT Serif / Source Sans 3, unchanged.
- PR Changes rendered Markdown diff (document): Source Sans 3 / Source Sans 3 before (broke the rule), PT Serif / Source Sans 3 after.
- Plugin md-body view without KPress (document): Source Sans 3 / Source Sans 3 before (broke the rule), PT Serif / Source Sans 3 after.
- PR description, comment, review, review-thread comment, and plain stand-in; commit body (chrome): Source Sans 3 / Source Sans 3, unchanged, now through .chrome-prose.
- KPress footnotes and tooltips inside a document: sans, KPress typography, out of scope.
The system font set follows the same pattern: ui-serif (Georgia) against system-ui. Probe and outputs: attic/font-probe.mjs, attic/inventory-before.txt, attic/inventory-after.txt.

Tests: test_serif_is_only_for_documents (which rules may set a face; chrome-prose builder registry); tests/dom/github-pull-first-paint-behavior.js (production PR texts carry the class); tests/test_prose_faces_chrome.py with tests/dom/prose-faces-chrome.mjs (computed and drawn faces, 2 reading fonts x 2 font sets, 44 checks; failed on main's CSS in exactly the 3 broken cases); parity row shell.prose-faces.
