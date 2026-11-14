---
type: is
id: is-01m1d3qcqc15jmht1zm496mjqb
title: Provider contract returns browser wire models for rollup and navigation
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-pluggable-inventory-engine.md
labels: []
dependencies: []
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
created_at: 2026-08-31T23:50:56.989Z
updated_at: 2026-11-14T18:45:00.243Z
---
The inventory provider contract imports two browser wire TypedDicts (src/metabrowser/inventory_engine/contract.py:95), against the pluggable-engine plan's rule that the contract does not expose HTTP models:

- RollupProjection.payload (contract.py:1237-1239) is RollupResult, whose RollupDirNode.children is list[Any] | None (wire_models.py:249) and whose mtime is float seconds (wire_models.py:246), while the rest of the boundary uses mtime_ns: int.
- NavigationProjection.payload (contract.py:1246-1248) is NavigationTallies, whose extensions, canonical_extensions, type_families, type_presets and recency_tallies are list[list[object]] (wire_models.py:261-265): positional rows with no stated arity or order. ExtensionTallyRow (wire_models.py:253) is the precise type and is not used.
- Building RollupResult needs metabrowser.inventory_rollup.build_rollup (744 lines of browser presentation logic: top/rest bucketing, dominant-extension selection, file-type breakdown).

A second provider (mb-hej8, fdu) would have to emit the browser's row layout and reimplement build_rollup on exactly the aggregate paths it exists to accelerate.

Direction: give the contract its own flat aggregate types (a bounded node list with parent indices, mtime_ns throughout, named tally row types) and move build_rollup's presentation shaping into the route layer. Then add metabrowser.wire_models to the denylist in tests/test_inventory_provider_contract.py::test_protocols_are_structural_and_provider_neutral, which commit 690e13c9 left out because it fails today. (The dead metabrowser.inventory entry is already gone.)
