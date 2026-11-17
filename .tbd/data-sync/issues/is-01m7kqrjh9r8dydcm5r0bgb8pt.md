---
type: is
id: is-01m7kqrjh9r8dydcm5r0bgb8pt
title: "Inert TOC: skip headings with no layout box in the reading-line search, as KPress 0.3.8 does"
kind: task
status: in_progress
priority: 3
version: 3
delegate: claude-code@vm
labels:
  - kpress
dependencies: []
parent_id: is-01m7ksbsx0kcg5rk05fy23nxc5
hold: null
hold_until: null
created_at: 2026-11-17T03:10:44.776Z
updated_at: 2026-11-17T03:57:11.715Z
started_at: 2026-11-17T03:57:11.715Z
---
inert-toc.js#targetAtReadingLine (moved there from toc-intersection-fallback.js in jlevy/metabrowser#494) binary-searches heading tops like KPress toc.js. KPress 0.3.8 (jlevy/kpress#77) made its search step past headings whose rect is all zero, such as a heading inside a closed <details>, because their top says nothing about the reader's position. The untrusted-profile inert TOC still selects them. Port the same probe-forward step and pin it in tests/dom/markdown-inert-toc-session.js with a zero-box heading.

## Notes

2026-11-17: Review A (GitHub review 5932482622) on jlevy/metabrowser#494 raised this as finding A4 (Low): CHANGELOG.md:9 says the TOC steps past headings inside a closed disclosure, which holds only for trusted renders; inert-toc.js:34 still selects a zero-box heading (headings at -500, hidden, 900 with the reading line at 250 pick the hidden one). Addressed in #494.
