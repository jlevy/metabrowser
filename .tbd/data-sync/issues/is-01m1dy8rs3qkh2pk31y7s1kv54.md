---
type: is
id: is-01m1dy8rs3qkh2pk31y7s1kv54
title: "Walker builds each entry twice: contract InventoryEntry then provider FsEntry"
kind: task
status: open
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-09-01T07:34:49.378Z
updated_at: 2026-09-04T01:30:12.371Z
---
H72: the walker builds each entry twice (contract InventoryEntry, then provider FsEntry via _internal_entry). Confirmed as the largest remaining per-entry cost, and it also carries two require_canonical_inventory_path calls per entry (path and parent) that vanish with it.

BLOCKED ON MODULE PLACEMENT, attempted 2026-09-03. Making walk_tree yield FsEntry directly is a mechanical swap -- FsEntry has matching for_observed_file/dir/symlink factories and _internal_entry already short-circuits on isinstance -- but FsEntry lives in metabrowser.events, and tests/test_python_inventory_provider.py::test_scanner_and_reducer_do_not_depend_on_browser_events forbids walker.py from importing it. That test is right: events.py is the browser-delivery module and its own docstring says providers never return FsEntry.

So H72 depends on mb-ed9h (R3.6): move the provider's retained record into providers/, or into a low-level module both the walker and the provider may import. Do that first, then this is a small change.

Measured context: on a real 300k-entry tree (/Users/levy/wrk/aisw/trading), main 42,004ms vs this stack 48,738ms, n=5, disjoint ranges: a separable +16.0% still outstanding.
