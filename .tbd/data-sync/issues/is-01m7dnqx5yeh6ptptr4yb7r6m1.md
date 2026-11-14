---
type: is
id: is-01m7dnqx5yeh6ptptr4yb7r6m1
title: Markdown wiki heading anchors render an empty paragraph before every heading
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-14T18:39:59.165Z
updated_at: 2026-11-14T18:40:06.071Z
started_at: 2026-11-14T18:40:06.069Z
---
Found while fixing mb-orvr (2026-11-14). The Markdown plugin's wiki parser (src/metabrowser/builtin_plugins/markdown/wiki-parser.js, around line 104) inserts `<span class="metabrowser-wiki-heading" id="obsidian-heading-…"></span>` plus a line ending on its own line before every heading, so the rendered document has an empty `<p>` before each heading. It is zero height and margins collapse through it mid-document, but it defeats `static/styles.css` `.metabrowser-kpress-host .kpress-prose > h1:first-child { margin-block-start: 0 }`: a document's title h1 keeps its 32 px top margin inside the card's 40 px padding (computed margin-top 32px in Chrome and WebKit), and any other first-child or sibling rule sees a stray paragraph.

Done when the heading anchors no longer create an extra block (the anchor ids still resolve for wiki links and in-page navigation, including the hierarchical `obsidian-heading-A#B` ids and their de-duplication), a document's first heading gets the first-child trim in both reading fonts, the parser's output budget accounting still holds, and a test pins both: no empty paragraph before a heading, and the anchor targets still work.
