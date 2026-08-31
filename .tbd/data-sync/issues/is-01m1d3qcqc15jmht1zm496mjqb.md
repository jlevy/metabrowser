---
type: is
id: is-01m1d3qcqc15jmht1zm496mjqb
title: Provider contract returns browser wire models for rollup and navigation
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-31T23:50:56.989Z
updated_at: 2026-08-31T23:50:56.989Z
---
The inventory provider contract is provider-neutral except for three projection payloads, which are browser wire TypedDicts imported from metabrowser.wire_models:

- RollupProjection.payload is RollupResult, whose RollupDirNode.children is 'list[Any] | None' (an untyped recursive tree) and whose mtime is a float second timestamp, while every other time on the boundary is mtime_ns: int.
- NavigationProjection.payload is NavigationTallies, whose extensions/canonical_extensions/type_families/type_presets/recency_tallies are 'list[list[object]]' -- positional rows whose arity and element order appear nowhere in the contract. ExtensionTallyRow, defined immediately above in the same file as tuple[str, int, int, int, int], is the precise type that is not used.
- Building RollupResult requires metabrowser.inventory_rollup.build_rollup (732 lines of browser presentation logic: top/rest bucketing, dominant-ext selection, file-type breakdown).

Consequence for a native provider: it must emit the browser's JSON row layout, including undocumented positional shapes, and reimplement build_rollup. These are the aggregate paths a native provider exists to accelerate, so this is the coupling that matters most.

Note that tests/test_inventory_provider_contract.py::test_protocols_are_structural_and_provider_neutral already asserts contract.py is provider-neutral, but its denylist is {starlette, metabrowser.events, metabrowser.inventory, metabrowser.sse} -- it misses metabrowser.wire_models, and metabrowser.inventory no longer exists, so that entry is dead.

Suggested direction: give the contract its own flat aggregate types (a bounded node list with parent indices rather than nested children; mtime_ns everywhere; named tally row dataclasses), and move build_rollup's presentation shaping into the route layer where the PR's own ownership table already puts it. Then add metabrowser.wire_models to the neutrality denylist and drop the dead entry.
