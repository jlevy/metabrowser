---
type: is
id: is-01m1mv9z8t171pvtrg1bcr7g86
title: "PR #101 R3.2: contract needs stated version-retention semantics"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:44.089Z
updated_at: 2026-09-03T23:57:44.089Z
---
DEFER (contract text, before the fdu adapter). assemble_tree_pages assumes a provider can still hold a pinned version. The Python provider honors pins at the tip plus a 64-entry FIFO page-memo table (python_inventory.py:1104-1107, 1379-1397); one bulk consumer can evict another's continuation. fdu retains NO historical image: any commit invalidates every outstanding continuation. Either guarantee bounded retention or drop multi-page pinned assembly. Sharpest Metabrowser/fdu mismatch on the books.
