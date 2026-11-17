---
type: is
id: is-01m7kqrjh9r8dydcm5r0bgb8pt
title: "Inert TOC: skip headings with no layout box in the reading-line search, as KPress 0.3.8 does"
kind: task
status: open
priority: 3
version: 1
labels:
  - kpress
dependencies: []
created_at: 2026-11-17T03:10:44.776Z
updated_at: 2026-11-17T03:10:44.776Z
---
inert-toc.js#targetAtReadingLine (moved there from toc-intersection-fallback.js in jlevy/metabrowser#494) binary-searches heading tops like KPress toc.js. KPress 0.3.8 (jlevy/kpress#77) made its search step past headings whose rect is all zero, such as a heading inside a closed <details>, because their top says nothing about the reader's position. The untrusted-profile inert TOC still selects them. Port the same probe-forward step and pin it in tests/dom/markdown-inert-toc-session.js with a zero-box heading.
