---
type: is
id: is-01m7vcqgjwkr50hfknj74hvddz
title: Lay inert Markdown documents' Mermaid diagrams out in the diagram frame
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T02:31:51.131Z
updated_at: 2026-11-20T02:31:51.131Z
---
An inert (untrusted) Markdown document's Mermaid diagrams are still laid out in the page
(`drawDiagrams(root, {inert: true})`, KPress image placement), where the diagram's own
CSS is live. On an `--untrusted` page the page's `img-src` admits the page's own origin,
so a diagram can make a same-origin request while Mermaid lays it out.

Found in review B of PR 616 (bead mb-l0ic): on an `--untrusted` page, a `stateDiagram`
with `classDef x mask-image:url(/api/file?path=…)` drawn with `inert: true` made a
same-origin GET that was answered 200, because the `/api` guard accepts
`Sec-Fetch-Site: same-origin`. The same source drawn with `isolated: true` (the diagram
frame, `builtin_plugins/markdown/diagram-frame.js`) made no request.

Likely fix: route inert document renders through the diagram frame as pull-request text
already is (`mode: "isolated"` in `markdown/diagrams.js`, chosen in `place-rendered.js`,
`rendered.js`, and `transclusion.js`), then extend `tests/dom/markdown-diagrams-chrome.mjs`
with a same-origin `/api` channel. Note that the frame measures a sequence diagram's actor
names in Mermaid's face where the page measures them in the app's, so those sizes change
slightly.
