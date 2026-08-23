---
type: is
id: is-01m0pmk1fp1pwemeahjawzn5ex
title: "H55: the campaign's numbers span seven corpora and none of them compare"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-23T06:23:08.264Z
updated_at: 2026-08-23T06:23:08.264Z
---
Across 48 recorded runs the loop used seven different corpora (.bench/corpus-300000, two synthetic sizes with no corpus label, tree-585f5500, two revisions of tree-a01f4187, and tree-e167d99b). Each round measured its own control against its own candidate, which is sound per round, but it means no number in report.md can be placed on the same scale as any other, and the campaign as a whole has never been measured.

The fix is a retroactive sweep: hold the corpus and the eval harness at today's version and move only src/metabrowser to each checkpoint. That is the property the corpus was designed for.

Metric: every checkpoint's standing metrics recorded against one corpus with one harness, so a single table shows what the campaign bought.

Answered by exp-010.
