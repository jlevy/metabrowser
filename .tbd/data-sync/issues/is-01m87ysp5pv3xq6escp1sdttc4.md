---
type: is
id: is-01m87ysp5pv3xq6escp1sdttc4
title: "Docs tab mounts a large new Markdown document whole: #31 of investment-research builds 72k nodes and freezes 4x350 ms"
kind: bug
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m87zs9sbky91edkksae1vbdt
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-11-24T23:38:29.940Z
updated_at: 2026-11-25T03:54:43.026Z
started_at: 2026-11-24T23:57:42.485Z
---
Measured 2026-11-24, runtime 19cd5a41 (main dcb9f32), headless Chrome 1280x900, finterm-ai/investment-research PR 31 (one new 876,516-byte Markdown book, 17,177 lines; 13 files).

Per tab after load (main-thread task time, DOM nodes, long tasks):
- Overview/Conversation: 0.26 s, 1.4-2.4k nodes, none
- Checks: 0.23 s, 1.4k nodes, none
- Changes: 0.5-1.0 s, 5-20k nodes, none
- Docs: 5.4-7.9 s, 72k nodes, 320,474 px tall, 9 long tasks totalling 1.8 s, four of 326-391 ms

Cause: rendered Markdown mounts every block of a file (diff-markdown.js load -> appendBlocks -> replaceChildren). Folds only hide unchanged context runs, and a new file is all added blocks; Current (unfold) shows whole documents by design. The 1 MiB _MARKDOWN_PAIR_MAX_BYTES cap admits this file; its comment says the page cost at the cap was never measured. Amplifier: every rendered-file mutate (diff-view.js mutate hook) runs placeOfTopFile, then holdPlace getBoundingClientRect, then notifyCurrentFile, each forcing a full layout of the 72k-node page (holdPlace 412 ms self in the profile), once per file state change.

After load interactions are 50-150 ms per relayout (Diff/Current, collapse, resize). content-visibility:auto on .diff-markdown-block did not change layout (2.3-3.0 s either way). WebKit (the macOS app) not yet measured.

Fix candidates: (1) draw rendered blocks near the viewport with reserved height, the policy the diff view already follows for source; (2) until then, a measured block/byte bound past which a rendered document opens its first chunk and grows on demand; (3) skip or coalesce the place hold when the changed file sits below the viewport, one measurement per frame. Separate: /api/catalog answered 12.4 MB in 2.8 s at this repo start.

## Notes

PR #811 (claude/rendered-markdown-modes). Rendered Markdown chooser is Full | Concise | Source; a file within WHOLE_UNITS/WHOLE_BYTES (= FULL_MAX_BLOCKS/FULL_MAX_BYTES, 500 blocks / 512 KiB) is drawn whole, a longer one a chunk at a time (CHUNK_UNITS 100 / CHUNK_BYTES 128 KiB) over spacers estimated at BLOCK_PX 20 + BYTE_PX 0.24 a byte, FOLD_PX 36.

Measured 2026-11-24, headless Chrome 152 1280x900, load average 270-330, origin/main vs branch, back-to-back pairs: reaching #31's 3,408-block book on Docs, worst task 351-352 -> 62-64 ms, task 0.48-0.52 -> 0.15-0.19 s, layout 0.165 -> 0.006 s; on Changes, worst 361-437 ms -> none over 50 ms, task 0.44-0.55 -> 0.07-0.09 s.

Not fixed here: the Docs page load itself (4.0-4.2 s, 72k nodes in both builds) comes from the book's Source body drawn at load while its rendered view waits -> mb-qzgs. Item 3 of the fix candidates (skip the place hold below the pane) was measured and dropped: scroll task 1.175-1.178 s with it, 1.195-1.223 s without. WebKit not measured.
