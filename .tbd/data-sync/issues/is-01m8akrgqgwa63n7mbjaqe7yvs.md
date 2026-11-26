---
type: is
id: is-01m8akrgqgwa63n7mbjaqe7yvs
title: Guided Review reads a neighbor step's documents ahead, so a document step shows at once
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-26T00:23:20.553Z
updated_at: 2026-11-26T00:23:20.553Z
---
Follow-up to mb-7bu6. Guided Review reads the steps next to the one shown ahead (guide-reads.js), but a step that cites a file whole (a document) draws it only as the step is shown: guided-review.js composes the step out of sight and waits on the diff plugin's mountRenderedFile, which asks the rendered route (pull-rendered-diff) then. On the stand-in, stack 70's document step took 134 to 352 ms from the press with its answer read ahead (rendered route 53 to 172 ms server time), and a kept document step 23 to 54 ms, since its documents are drawn again; meanwhile the step left stays and the arrows' delayed mark shows. Read a neighbor step's documents' rendered layers ahead too, through the diff plugin (as prefetchMarkdown does for Changes' first screen, with prefetch=1), or keep a shown step's drawn documents, so a document step next to the one shown is as warm as any other. tests/dom/github-guided-review-motion-chrome.mjs then records those two scenarios as warm (true) rather than "documents".
