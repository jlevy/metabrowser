---
type: is
id: is-01m0t8q47y0evpx16xrxfpr036
title: Restore bounded-staleness navigation reads in Python provider
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - performance
dependencies: []
parent_id: is-01m0t8bsb54j16rhfdmwj5q0vh
created_at: 2026-08-24T16:12:36.989Z
updated_at: 2026-08-24T16:50:28.602Z
closed_at: 2026-08-24T16:50:28.600Z
close_reason: Implemented the coherent bounded-staleness root-navigation read memo with deterministic regression coverage; 100,000-file navigation memo p50 improved from 44.1 ms to 0.8 ms and make verify passes.
resolution: null
duplicate_of: null
---
PR 73 made repeated navigation polling during an active walk reuse a fresh-enough tally before copying or traversing the whole index. The provider refactor routes every NavigationQuery through _capture_image, which copies all entries and keys the memo strictly by the moving revision. Restore the stale-safe fast path inside the provider implementation while preserving one-version bundled reads, provider scheduling ownership, and accurate WorkCounters. Add a deterministic bundled-read regression test covering repeated navigation reads during a revision change.

## Notes

Implemented a coherent Python-provider root-summary read memo. During discovery, a cache hit returns the retained version/cursor/state/root entry and recalculates only recency rows from retained sorted mtimes; WorkCounters report zero entries visited. Finalized/live revision changes force an exact refresh. Focused provider and upstream staleness tests pass.
