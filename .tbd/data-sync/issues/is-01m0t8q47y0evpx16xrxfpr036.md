---
type: is
id: is-01m0t8q47y0evpx16xrxfpr036
title: Restore bounded-staleness navigation reads in Python provider
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - performance
dependencies: []
parent_id: is-01m0t8bsb54j16rhfdmwj5q0vh
created_at: 2026-08-24T16:12:36.989Z
updated_at: 2026-08-24T16:12:36.989Z
---
PR 73 made repeated navigation polling during an active walk reuse a fresh-enough tally before copying or traversing the whole index. The provider refactor routes every NavigationQuery through _capture_image, which copies all entries and keys the memo strictly by the moving revision. Restore the stale-safe fast path inside the provider implementation while preserving one-version bundled reads, provider scheduling ownership, and accurate WorkCounters. Add a deterministic bundled-read regression test covering repeated navigation reads during a revision change.
