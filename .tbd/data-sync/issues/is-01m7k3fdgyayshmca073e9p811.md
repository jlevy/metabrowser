---
type: is
id: is-01m7k3fdgyayshmca073e9p811
title: "Chrome flake: tests/test_prose_faces_chrome.py fails with 'CSS.getPlatformFontsForNode: Could not find node with given id' (tests/dom/prose-faces-chrome.mjs:310)"
kind: bug
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
child_order_hints:
  - is-01m7kascwqcptg9j4rbqasg2ck
hold: null
hold_until: null
created_at: 2026-11-16T21:16:13.212Z
updated_at: 2026-11-16T23:24:00.278Z
started_at: 2026-11-16T21:17:12.907Z
---
Seen on #452 at ac20c2c28 (Actions run 43950596471, test (3.14t); 6496 passed, 67 skipped) and noted by the mb-alff fix as a separate race. The driver asks CDP for a node's platform fonts after the node can be replaced. Find the replacing paint, then either hold the node or re-resolve it by selector and retry once with a stated reason; prove with a loaded-machine loop (the mb-alff 6x CPU-throttle method).
