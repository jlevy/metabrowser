---
type: is
id: is-01m03awqw5frn5zgcw5q074pyx
title: "Text preview: measure whether content-visibility helps past 16 MiB"
kind: task
status: closed
priority: 3
version: 3
spec_path: docs/large-content-rendering.md
labels: []
dependencies: []
created_at: 2026-08-15T18:28:06.149Z
updated_at: 2026-11-14T18:41:59.261Z
closed_at: 2026-11-14T18:41:59.260Z
close_reason: "Duplicate of mb-1bh1 (H99): content-visibility chunks for long source views, measured with find-in-page checked; its measurements are superseded by docs/large-content-rendering.md's 2026-11-12 runs."
resolution: duplicate
duplicate_of: is-01m774rb30k3bd8ehwy6exbwq4
extensions:
  linear:
    id: 53578099-acf6-4206-90ba-36f3434b1448
    linked_at: 2026-08-16T08:05:43.503Z
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
