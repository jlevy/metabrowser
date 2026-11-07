---
type: is
id: is-01m6sqgkmrvgmdx0htfvr7xnv3
title: Load diff patches ahead of scrolling without a routine counter
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T00:46:08.529Z
updated_at: 2026-11-07T00:59:17.466Z
started_at: 2026-11-07T00:47:31.173Z
---
Keep all known changed file names available from the manifest, keep the first patch batch fast, and start a small cancellable lookahead for later patches. Remove the normal loaded-of-total message. Preserve useful per-file spinner, failures, actual truncation guidance, explicit jumps and bounded work on large diffs.

## Notes

Implemented scroll-root lookahead and removed the routine counter. Browser test of a 55-file comparison showed file 51 ready 105 px below the viewport and file 55 reachable. Independent review reproduced and fixed heading scroll movement and a stale nearby request after patch growth. Thirteen focused pytest cases and six golden cases passed.
