---
type: is
id: is-01m1mv9z8t171pvtrg1bcr7g86
title: "PR #101 R3.2: contract needs stated version-retention semantics"
kind: task
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:44.089Z
updated_at: 2026-09-08T00:02:48.099Z
closed_at: 2026-09-08T00:02:48.098Z
close_reason: ReadRequest now states exact-or-unavailable retention semantics. Python continuation memos retain immutable rows/state across live updates; Directory, FilteredTree and Catalog mutation cases plus explicit eviction regression pass. Native churn/eviction acceptance is retained as a gate in mb-hej8.
resolution: null
duplicate_of: null
---
DEFER (contract text, before the fdu adapter). assemble_tree_pages assumes a provider can still hold a pinned version. The Python provider honors pins at the tip plus a 64-entry FIFO page-memo table (python_inventory.py:1104-1107, 1379-1397); one bulk consumer can evict another's continuation. fdu retains NO historical image: any commit invalidates every outstanding continuation. Either guarantee bounded retention or drop multi-page pinned assembly. Sharpest Metabrowser/fdu mismatch on the books.

## Notes

Review found the Python page memo already retains immutable rows and state but rejects them after any engine advance. Removing that redundant current-version gate allows coherent continuation under filesystem churn without retaining another index. Document bounded eviction and require VersionUnavailableError after eviction; add continuation-after-mutation coverage for directory, filtered tree, and catalog pages.
