# Review: The Pluggable Inventory Engine, Merged with Current Main

**Date:** 2026-08-31

**Author:** Reviewer (LLM-assisted)

**Status:** Complete.
Three defects were found and fixed on the branch; three design findings are open as
beads.

**Scope:** [PR #74](https://github.com/jlevy/metabrowser/pull/74) at `3183888`, merged
with `origin/main` at `26b109e` — 130 commits, including the CLI parity mechanism, the
released 0.9.0, and the Git history work.
The question asked was whether the boundary this refactor introduces is clean enough
that the performance-sensitive engine could later be replaced by a native
implementation.

Read: [the contract](../../../src/metabrowser/inventory_engine/contract.py), the
coordinator, the Python provider, the
[provider architecture](../architecture/arch-inventory-provider.md), the
[conformance suite](../../../tests/test_inventory_provider_contract.py), and the routes
and CLI modes that consume the boundary.
Route behaviour was reproduced against a running server rather than read from the code,
which is how the three defects surfaced.

## Verdict

**The boundary is the right shape and the right size, and it is not yet provider-neutral
where neutrality matters most.**

`InventoryHandle` is five methods.
Reads are batched — one call carries many queries and returns one coherent version —
which is exactly the shape that makes a foreign-function boundary cheap.
Every query is bounded, every projection is validated on construction, the lifecycle is
an explicit transition graph, and the coordinator retains no mirror of the inventory.
A conformance suite parametrized over registered backends means adding a second provider
is one tuple entry and twelve cases run against it.
This is better than most abstraction boundaries survive contact with.

The gap is narrow and specific.
Of eight projections, five are contract-owned types built from primitives.
The other three — rollup, navigation, and the aggregate paths generally — return
**browser wire models**, imported into the contract from `metabrowser.wire_models`.
Those are the paths a native engine exists to accelerate.
A native provider must therefore emit the browser’s JSON row layout, including
positional rows whose element order the contract never states, and reimplement 732 lines
of presentation logic to do it.

Fixing that is a bounded change to three types, and it should happen before the second
provider is written rather than after.

## What the merge required

Five files conflicted.
Four were both sides adding adjacent things.
The fifth was the lifespan, where this branch made the runtime application-scoped and
main added a Git history-session shutdown; both obligations are kept.

Reconciling the two sides surfaced three defects that neither side had alone.
All three are fixed on the branch, each confirmed to fail against the code before its
fix.

### D1 — A wire path reached the provider verbatim

`_safe_path` answers a filesystem question: is this inside the root.
The contract asks a different one: is this a canonical inventory key.
Nothing bridged them, so client-supplied spellings went straight into contract queries.

| Request | Before | After |
| --- | --- | --- |
| `/api/tree?path=docs/` | `500` | `200` |
| `/api/rollup?path=docs/` | `500` | `200` |
| `/api/file?path=docs/` | `200`, crash logged behind it | `200` |
| `/api/rollup?path=.` | `404` | `200`, the root rollup |
| `metab --walk --path docs/` | traceback | the subtree |
| `metab --walk --path .` | empty tree, no error | the whole tree |
| `POST /api/diagnostics/pending-tallies` | `500` on any non-canonical sample path | the path is dropped |

The `/api/file` row is the worst of these: a broad `except Exception` turned a contract
violation into an HTTP 200 carrying a degraded error body, so nothing upstream could
notice.

`canonical_inventory_path` now performs the translation once, above the boundary.
A provider only ever receives what `require_canonical_inventory_path` accepts, which is
the property a second implementation depends on and which the new tests assert directly.

`.` was also **accepted by the validator it should have failed**. `PurePosixPath(".")`
has empty `parts` and an `as_posix()` equal to itself, so both structural checks passed.
The root has exactly one key, `""`; admitting a second spelling is what let `.` reach a
provider as a path matching nothing.
A native provider using different path normalization would very likely have resolved `.`
to the root, and the two engines would have disagreed on an input no test covered.

### D2 — The catalog ETag followed the wrong clock

The engine version and the catalog are different clocks.
Every indexed change advances the engine version; the catalog carries a path and a
logical extension per file and moves on far fewer.

Keying the client-facing ETag on the engine version meant an ordinary editor save
re-sent the entire catalog — up to `max_files` rows, the largest payload the server
produces — to every connected client.
Measured on a settled tree, an mtime-only touch left the wire file list byte-identical
and changed the ETag anyway; the only differing byte in the response was the `revision`
field claiming it had changed.

The ETag now derives from content identity.
The engine version is retained as what it is genuinely good at: a constant-work
checkpoint that lets a repeat poll answer without assembling the catalog at all.
`revision` is again the count of distinct catalogs served, which is what it meant before
this refactor and what the golden recorded.

This one is worth noting as a boundary lesson rather than a bug.
`CatalogProjection` carries no change identity, so the host cannot ask a provider
whether its catalog moved.
Deriving identity host-side is correct and cheap here; a provider that already knows the
answer should eventually be able to say so.

### D3 — `golden-update` silently re-pinned host facts

Commit `8cedf87` elided the watcher `reason` values by hand so the goldens would pass on
Linux rather than only on the author’s Mac.
Nothing restored those elisions, so the next `make golden-update` re-pinned `fs=apfs`.

`golden_fixup.py` restores them now, along with the engine sequence in the pending-tally
diagnostic, which counts internal change batches and is not a fact a transcript should
hold.
The script now keeps the promise its own docstring makes, that `golden-update` is a
single reviewable step.

## What is strong

These are worth stating explicitly, because they are the parts a second provider will
lean on.

**The handle is small and batched.** Five methods; `read` takes many queries and returns
one coherent version, cursor, lifecycle state, and work record.
A native binding crosses the boundary once per read, not once per query.

**Bounds are separated rather than conflated.** The discovery file budget, per-page row
bound, aggregate query bound, lifecycle issue bound, and read-bundle bound are distinct
constants. Conflating them is the usual way a boundary like this becomes unimplementable
at scale.

**The lifecycle is a real state machine.** `ALLOWED_PHASE_TRANSITIONS` is total over the
phase set, terminal states are terminal, and a test asserts both.
`ready` distinguishes an open idle handle from `watching`, which requires a live
observer — a distinction a native provider needs and would otherwise have to guess.

**Invalidation is resumable with explicit reset.** `changes(after=cursor)` with a typed
gap reset is the right primitive for a foreign provider: it can be implemented over a
poll or a channel without an event loop on the other side.

**The conformance suite enforces its own integrity.** A meta-test asserts every
registered conformance case is factory-parametrized, so a Python-only test cannot be
added to the registry.
Another asserts the architecture document lists every case.
The registry is maintained rather than aspirational.

**The coordinator holds no mirror state.** Lifecycle, versioning, a bounded change
history, and subscriber sets — no entry mirror.
Host decorations live in a sparse path-keyed overlay that a provider never sees.
This is the rule most refactors of this kind break, and it holds here.

## Open findings

### F1 — The contract returns browser wire models on the aggregate paths

Tracked as `mb-gwlw`.

`contract.py` has exactly two non-standard-library imports: `metabrowser.constants`, and
`metabrowser.wire_models`. The second is the browser’s JSON response layer.

- `RollupProjection.payload` is `RollupResult`, whose `RollupDirNode.children` is
  `list[Any] | None` — an untyped recursive tree — and whose `mtime` is a float second
  timestamp, while every other time on the boundary is `mtime_ns: int`.
- `NavigationProjection.payload` is `NavigationTallies`, whose `extensions`,
  `canonical_extensions`, `type_families`, `type_presets`, and `recency_tallies` are all
  `list[list[object]]`: positional rows whose arity and element order appear nowhere in
  the contract. Consuming code reads them as `ext, tracked, ignored = row[:3]`.
  `ExtensionTallyRow`, defined a few lines above in the same file as
  `tuple[str, int, int, int, int]`, is the precise type that is not used.
- Producing `RollupResult` requires `inventory_rollup.build_rollup`: 732 lines of
  presentation logic covering `top`/`rest` bucketing, dominant-extension selection, and
  the file-type breakdown.

The PR’s own ownership table puts serialization and browser policy in the route layer.
These three payloads are the exception, and they are the exception on precisely the
surfaces a native engine is meant to make fast.

There is a sharp way to see the size of this gap.
`test_protocols_are_structural_and_provider_neutral` already asserts the contract is
provider-neutral by checking its imports against a denylist.
The denylist does not include `metabrowser.wire_models`. The check encoding the right
idea is one entry away from failing, and that entry is the work.

Suggested direction: give the contract flat aggregate types — a bounded node list with
parent indices rather than nested `children`, `mtime_ns` throughout, named tally-row
dataclasses — and move `build_rollup`’s shaping into the route layer where the ownership
table already places it.
Then add `wire_models` to the denylist.

### F2 — `metab --walk --stream` bypasses the selected provider

Tracked as `mb-nc2x`.

`build_tree_envelope` (`--walk --all-at-once`) reads through the provider.
`stream_dump_lines` (`--walk --stream`) calls `walker.walk_tree` directly, bypassing the
coordinator and the selected backend.

With a non-Python provider selected, `--walk --stream` would stream the Python walker’s
records while the server served the other engine — the CLI describing an engine that is
not running, which is the failure the parity rule exists to prevent.

The streaming surface is documented as the walker’s record sequence, so this may be
deliberate. If it is, it should name which engine it reads and be excluded from provider
parity explicitly. Either way the decision belongs before a second provider lands.

### F3 — No conformance case pins the aggregate payload shape

Tracked as `mb-nqgs`.

The twelve registered conformance cases cover checkpoints, semantic parity, bounds,
paging, version pins, changes, verified refresh, lifecycle, sessions, and joined close.
None asserts the shape of the rollup and navigation payloads.

Because those payloads are `list[list[object]]` and `list[Any]`, a second provider can
satisfy every registered case and still return rows the browser cannot read: a tally row
with its elements in a different order, seconds where nanoseconds were expected, a
differently nested node.
Nothing in the suite would fail.

F1 and F3 are the same problem seen from two directions.
Fixing F1 makes F3 mostly mechanical, because a typed payload is a payload a conformance
case can assert.

## Testing added

Three files, each confirmed to fail against the code before its fix.

- `test_inventory_path_boundary.py` (48 cases) asserts the property a provider depends
  on: everything `canonical_inventory_path` accepts is already canonical by
  `require_canonical_inventory_path`, the translation is idempotent, equivalent
  spellings are indistinguishable at the routes, and no query string can raise out of
  the boundary.
- `test_inventory_debug_route.py` pins `/_debug/inventory`. Two tools parse that payload
  — the performance harness and `bench_serving` — and nothing asserted it.
  A renamed counter does not fail either tool; it blanks a benchmark column while
  looking fine, which is a bad failure mode for the surface that exists to justify an
  engine swap.
- A case in `test_catalog_feed_server.py` covers D2 from the direction the existing test
  did not: identity across a change the catalog does not carry.

`/_debug/inventory` also gained the parity row it needed, exempt for the reason
`/_debug/tasks` is: its work counters carry wall and CPU times that no transcript can
pin.

## Before the native provider is written

1. Settle F1. A native binding written against `list[list[object]]` will encode today’s
   positional layout by observation, and that becomes the contract by accident.
2. Settle F2, so every CLI mode names the engine it read.
3. Add F3’s conformance case, so the aggregate shape is pinned for every registered
   backend rather than for the one that happens to build it today.
4. Consider giving `CatalogProjection` a content identity.
   D2 was fixed host-side because the contract offers no way for a provider to report
   that a projection did not move.
   The host can always derive it; a provider that already knows should be able to say
   so.

The first spikes the PR proposes — one constant-work checkpoint, one coherent
directory-plus-rollup read, one mutation converging through `changes()` — are the right
three, and the second of them is exactly where F1 will be felt.

## Validation

`make verify` passes on the merged branch: 1,817 pytest cases, 99 golden scenarios,
lint, type checks, public hygiene, parity (26 covered, 5 exempt), supply-chain audits,
and distribution inspection.

## References

- [Inventory provider contract](../architecture/arch-inventory-provider.md)
- [Views, models, and routes](../architecture/arch-views-models-routes.md)
- [Phase 1 refactor and fdu adoption plan](../specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md)
- [fdu and Metabrowser inventory-engine alignment](../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
