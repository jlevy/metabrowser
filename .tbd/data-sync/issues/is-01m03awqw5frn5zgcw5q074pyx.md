---
type: is
id: is-01m03awqw5frn5zgcw5q074pyx
title: "Text preview: measure whether content-visibility helps past 16 MiB"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/large-content-rendering.md
labels: []
dependencies: []
created_at: 2026-08-15T18:28:06.149Z
updated_at: 2026-08-15T18:28:06.149Z
---
The source view now opens at 2 MiB and grows to 8 MiB per click, appending
rather than re-rendering. Measured on a 16 MiB source file: loads to
completion in three clicks at 298 ms / 574 ms / 1233 ms, scrolling flat at
19-33 ms, heap 29-57 MB, 295 DOM nodes.

It needs nothing further at that size: `white-space: pre` over natural lines
is already proportional to line count, so the quadratic wrap path the binary
view hit does not apply here.

Open question for a file an order of magnitude larger. The next rungs on the
ladder in docs/large-content-rendering.md are content-visibility blocks and
then virtualization. Measure before adding either; at 33 ms scroll there is
currently nothing to buy.
