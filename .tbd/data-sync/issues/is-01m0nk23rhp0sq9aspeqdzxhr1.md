---
type: is
id: is-01m0nk23rhp0sq9aspeqdzxhr1
title: Walk tracked files before ignored ones (H33)
kind: task
status: open
priority: 0
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T20:37:10.531Z
updated_at: 2026-08-23T00:06:11.136Z
---
Measured on the real 241k-file tree AFTER exp-006 landed, with the ignore check correctly wired:

  files indexed      241,084   of which 48% ignored
  directory yields   201,604   of which 59% ignored
  last TRACKED file seen at 29.94 s of the 30.06 s walk

That last line is the point. The walk is strict level-order, so tracked and ignored work interleave completely and the tracked tree -- the part a reader is looking at -- is not finished until essentially the whole scan is. About half the walk is spent below directories the reader has said they do not care about.

Crucially, BFS already gives the nav what it needs: walk_tree yields a directory placeholder BEFORE enqueueing it (walker.py around 417-439), so a top-level node_modules/ or .venv/ appears in the nav as soon as the root is scanned. The shape is complete early. Only the DESCENT into those subtrees is expensive.

So the change is narrow: keep yielding placeholders at the level they appear, but move ignored subdirectories to a secondary queue drained after the tracked frontier, rather than appending them to the same FIFO. Everything is still crawled; flags still control what is revealed; only the order changes.

Predicted: time until all tracked entries are indexed roughly halves; nav shape unchanged; total walk unchanged. Must compose with the level-order guarantee the walker documents (shallow dirs finalize first) rather than replace it -- a secondary FIFO preserves level order within each class.

Do NOT confuse with exp-006, which removed a different traversal entirely (the gitignore pattern pre-walk) and did not defer anything.
