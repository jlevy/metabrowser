---
type: is
id: is-01m7tb5hr58w6wt67a59yaqgjr
title: Review, land, and test end to end the Mermaid diagram PRs (jlevy/kpress#80, jlevy/metabrowser#597) on jlevy/markform
kind: task
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T16:45:19.492Z
updated_at: 2026-11-19T16:47:12.228Z
started_at: 2026-11-19T16:47:12.227Z
---
Owner, 2026-11-19, verbatim: "can you review and make sure all the mermaid diagram PRs are reviewed and merged as well and let me test end to end" and "let's use the jlevy/markform repo as an example for testing as it has a mermaid document on the readme". #597 depends on kpress#80 (builds KPress from claude/diagrams-mermaid-mode via [tool.uv.sources]; publish.yml refuses a release while a source is set). Plan tracked under mb-qz51.

## Notes

2026-11-19 E2E on jlevy/markform README with #597 a431e686a (kpress 5037f8a), served as a GitHub URL: the flowchart renders in image placement and is broken (labels overlap, subgraph boxes collapse). Console: page CSP style-src (static, plugin-static, kpress-static only) blocks an inline style twice — likely the image placement's measurement host. Screenshot attic/mermaid-e2e/markform-readme-597-a431e686a.jpg. Merge held until fixed and the markform rerun matches GitHub. Reviews running for kpress#80 and #597; owning session 'Mermaid diagram rendering parity' notified.
