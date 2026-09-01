---
type: is
id: is-01m1dy8rs3qkh2pk31y7s1kv54
title: "Walker builds each entry twice: contract InventoryEntry then provider FsEntry"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-09-01T07:34:49.378Z
updated_at: 2026-09-01T07:34:49.378Z
---
Registered as H72 in the load-time plan. The last measurable item on the inventory scan profile, and the same duplication the design review names as F1 (mb-gwlw).

walk_tree yields a contract InventoryEntry, which validates its path and its parent on construction. The Python provider immediately converts it to FsEntry via _internal_entry, and converts back to InventoryEntry when a read crosses the boundary. So a first walk constructs every entry twice and validates its path four times: 124,420 validations from InventoryEntry.__post_init__ plus 124,406 from ChangeBatch.__post_init__ over a 60,000-file corpus.

Worth about 190 ms by microbenchmark -- InventoryEntry construction 1.85 us x 62,210, plus _internal_entry 1.23 us x 62,210. That is above what the host can resolve, unlike every other remaining candidate on the profile, all of which were rejected in exp-023 for being under the noise floor.

Approach: walk_tree has four construction sites and four consumers, two of them the CLI walk surfaces. Threading a record factory through it would let the provider build FsEntry directly while the CLI keeps the contract type. This is a contract-shaped change, not a local one, which is why exp-023 stopped short of it.

Re-measure with explorations/performance-loop/scan_bench.py, which interleaves conditions now -- see exp-023 for why that matters.
