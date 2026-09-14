---
type: is
id: is-01m2ff9v65wdpfdenh8f4gd2k5
title: Wiki link resolution scales superlinearly with link count and source path length
kind: bug
status: open
priority: 2
version: 1
labels:
  - performance
  - markdown
dependencies: []
created_at: 2026-09-14T08:07:26.660Z
updated_at: 2026-09-14T08:07:26.660Z
---
Wiki link resolution in the Markdown link enhancer scales superlinearly with document size.

Found while stabilizing load-sensitive tests (PR #119): the browserless test `tests/test_rendered_markdown_link_enhancer*` takes 13.4 s at load average 9 and 19 s at load 26 against its 30 s pytest timeout, and has timed out several times under load. A profile puts nearly all the time in the product's `wiki-resolver.js`, in one block that resolves 4,096 wiki links against a 20,409-character source path. It is superlinear: 1,024 links take 1.2 s, and a 5,100-character path takes 0.1 s.

Do:
1. Profile the resolver on that fixture and identify the superlinear step (likely per-link work proportional to source path length or to the number of links, e.g. repeated normalization, splitting, or candidate scans).
2. Fix the product cost so resolution is linear in links and path length, with a work-counter test (not wall clock) that pins the bound, following docs/large-content-rendering.md (measure before bounding).
3. Confirm the browserless test drops well below its timeout without shrinking its coverage.
