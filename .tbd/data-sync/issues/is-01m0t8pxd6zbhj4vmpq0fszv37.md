---
type: is
id: is-01m0t8pxd6zbhj4vmpq0fszv37
title: Record and automate previous-release performance comparisons
kind: feature
status: closed
priority: 1
version: 3
labels:
  - performance
  - testing
dependencies: []
created_at: 2026-08-24T16:12:29.989Z
updated_at: 2026-08-24T16:29:56.974Z
closed_at: 2026-08-24T16:29:56.969Z
close_reason: Recorded post-merge v0.6.0 comparison as exp-015, added atomic comparator JSON output, documented the reusable previous-release loop, and added it to publishing policy.
resolution: null
duplicate_of: null
---
Commit the post-merge v0.6.0 versus bae51fd cold-start evidence, including responsiveness and stability caveats. Add a repeatable workflow that identifies both builds, keeps output in one run directory, executes paired backend comparisons, and prepares browser conditions with explicit provenance so future releases can be compared without reconstructing ad hoc commands.
