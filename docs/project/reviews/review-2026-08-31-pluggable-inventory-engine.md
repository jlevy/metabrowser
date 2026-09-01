# Review: The Pluggable Inventory Engine

**Date:** 2026-08-31

**Author:** Reviewer (LLM-assisted)

**Status:** Complete.
Five defects were found and fixed while merging, and a 2.75x performance regression
against `main` was measured and mostly closed; seven findings are open as beads.
The stack is restacked so each branch merges into the one below it.

**Scope:** The whole inventory-engine stack, merged onto current `main` and reviewed as
one artifact:

| Branch | Head | Contributes |
| --- | --- | --- |
| `codex/fdu-backend-alignment-research` | `2feaa7bd` | the provider contract, coordinator, and Python provider |
| `codex/fdu-opened-root-e2e-spike` | `0b7a7140` | the measured fdu adapter spike, the scope/policy split, lifecycle vocabulary |
| `codex/inventory-contract-alignment` | `287bc722` | total row orders, unconditional recency ranking, the total canonical encoding |

Merged with `origin/main` at `26b109e` — 130 commits, including the CLI parity
mechanism, the released 0.9.0, and the Git history work.

The question asked was whether the boundary this stack introduces is clean enough that
the performance-sensitive engine could later be replaced by a native implementation.

Read: the contract, coordinator, and Python provider; the
[provider architecture](../architecture/arch-inventory-provider.md); the conformance
suite; the [fdu adapter spike](../../../explorations/fdu-inventory-adapter/README.md)
and its recorded evidence; and the routes and CLI modes that consume the boundary.
Route behaviour was reproduced against a running server rather than read from the code,
which is how the defects surfaced.

## Verdict

**The boundary is the right shape and the right size.
It is not yet provider-neutral on the aggregate paths, and that is now measured rather
than argued.**

`InventoryHandle` is five methods.
Reads are batched — one call carries many queries and returns one coherent version —
which is exactly the shape that makes a foreign-function boundary cheap.
Every query is bounded, every projection is validated on construction, the lifecycle is
an explicit transition graph, and the coordinator retains no mirror of the inventory.
Nineteen conformance cases are parametrized over registered backends, so adding a second
provider is one tuple entry.
The alignment branch closes the remaining ambiguity a second implementation would have
discovered the hard way: row order is now stated and total, recency ranking is
unconditional, case folding is ASCII and says so, and the canonical path encoding is
total.

The spike already ran a real native engine against this contract.
Nine of twelve conformance cases passed unchanged; a tenth matched every filesystem
fact, order, aggregate, filter, and catalog record and failed only on the provider name.
That is a strong result, and it is the evidence that matters most here.

The gap is narrow, specific, and unchanged by the stack.
Of the projections the contract defines, most are contract-owned types built from
primitives. Rollup and navigation return **browser wire models**, imported into the
contract from `metabrowser.wire_models`. Those are the paths a native engine exists to
accelerate, and the spike measured what they cost: one bundled eight-query read
materialized 8,830 entries and 412,836 bytes of relative paths, rebuilt 470 child
buckets, performed four full-result sorts and four aggregate passes, and took about 852
ms. The spike’s own fourth recommendation — native filtered-tree and rollup projections
to remove the temporary Python entry graph — is this finding reached from the other
direction.

Fixing it is a bounded change to three types, and it should happen before the native
provider is written rather than after.

## What the stack contributes

Worth stating separately, because these are the parts that turn a plausible boundary
into one a second implementation can be held to.

**Row order is total.** The contract previously documented no row order at all.
Each provider’s order was discoverable only by reading its implementation, and ties were
settled by whichever sort it happened to use.
All three orders are now stated as total: breadth-first level order for directory and
filtered-tree pages, canonical path order for catalog pages, and two explicit orders for
recency — selection by ignored state then time then path, return by time then path.
Level order rather than pre-order is the right call for a bounded page: a pre-order page
cut at its bound can return one directory and a thousand descendants, leaving the caller
unable to tell whether the parent held two entries or two thousand.

**The canonical encoding is total, and it was hiding a crash.** `_child_order` sorted by
`row.name.encode("utf-8")`, but `os.scandir` decodes an undecodable byte into a
surrogate, and encoding a surrogate raises.
One such file made a whole directory unlistable, where fdu escaped it and listed it.
Undecodable bytes now become `%XX`, the mapping is injective, and all four order keys
canonicalize, so every order agrees with fdu byte for byte.

**Case folding names its alphabet.** `str.lower()` folds all of Unicode; fdu’s
`eq_ignore_ascii_case` folds only ASCII. `archive.TÜRKÇE` matched in one and was dropped
by the other — identical on ASCII, divergent beyond it, invisible until a corpus stops
being English. `ascii_casefold` states the alphabet and folds both sides of every
comparison.

**Scope is separated from execution policy.** `max_files` moved into `DiscoveryBudget`,
leaving `InventoryConfig` to describe semantic scope.
Two providers can then agree on what is in the inventory while disagreeing about how
hard to work discovering it.

**The spike is real evidence, honestly bounded.** It verifies the wheel digest, refuses
to import fdu from a sibling checkout, and records its own duplication rather than
hiding it. Its disposition — keep the probe, runner, and evidence; delete the adapter —
is the right call, and its conclusion that the measurement does not justify a generic
native query engine is the kind of negative result worth having recorded.

## What the merge required

Each branch was merged into the one below it rather than reconciled in one place, so
every pull request in the stack shows only its own work and passes its own gate.

Six files conflicted.
Five were both sides adding adjacent things.
The sixth was a genuine collision, and it is the most interesting finding here.

All five defects below are fixed, each confirmed to fail against the code before its
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
| `POST /api/diagnostics/pending-tallies` | `500` on a non-canonical sample path | the path is dropped |

The `/api/file` row is the worst: a broad `except Exception` turned a contract violation
into an HTTP 200 carrying a degraded error body, so nothing upstream could notice.

`parse_inventory_path` now performs the translation once, above the boundary.

`.` was also **accepted by the validator it should have failed**. `PurePosixPath(".")`
has empty `parts` and an `as_posix()` equal to itself, so both structural checks passed.
The root has exactly one key, `""`; admitting a second spelling is what let `.` reach a
provider as a path matching nothing.
A native provider using different path normalization would very likely have resolved `.`
to the root, and the two engines would have disagreed on an input no test covered.

### D2 — Two functions, one name, opposite directions

Both this branch and the alignment branch added a `canonical_inventory_path`, and they
are not the same operation.

- **Outbound**, from the alignment branch: a name the filesystem gave us becomes the
  canonical identity, escaping undecodable bytes as `%XX`. Total by construction.
- **Inbound**, from this review: a spelling a client sent becomes that same identity, or
  is refused because it names nothing.

Both are needed, so both are kept and the inbound one is renamed `parse_inventory_path`.

It ends by checking its result against `require_canonical_inventory_path` rather than
open-coding the same rules.
That is what makes the pair compose: the alignment branch’s new surrogate refusal
narrows the parser in the same commit that adds it, without the parser mentioning
surrogates. A client sending a raw platform name now gets a `404` rather than a `500`,
and that composition is asserted directly.

This collision is worth more than its size.
Two independent efforts reached for the same name for the two halves of one boundary
crossing, which is a fair sign that the crossing deserves both halves named and stated
together in the architecture document.

### D3 — The catalog ETag followed the wrong clock

The engine version and the catalog are different clocks.
Every indexed change advances the engine version; the catalog carries a path and a
logical extension per file and moves on far fewer.

Keying the client-facing ETag on the engine version meant an ordinary editor save
re-sent the entire catalog — up to the discovery budget in rows, the largest payload the
server produces — to every connected client.
Measured on a settled tree, an mtime-only touch left the wire file list byte-identical
and changed the ETag anyway; the only differing byte in the response was the `revision`
field claiming it had changed.

The ETag now derives from content identity.
The engine version is retained as what it is genuinely good at: a constant-work
checkpoint that lets a repeat poll answer without assembling the catalog at all.
`revision` is again the count of distinct catalogs served.

This is a boundary lesson as much as a bug.
`CatalogProjection` carries no change identity, so the host cannot ask a provider
whether its catalog moved.
Deriving identity host-side is correct and cheap here; a provider that already knows the
answer should eventually be able to say so.

### D4 — `golden-update` silently re-pinned host facts

Commit `8cedf87` elided the watcher `reason` values by hand so the goldens would pass on
Linux rather than only on the author’s Mac.
Nothing restored those elisions, so the next `make golden-update` re-pinned `fs=apfs`.

`golden_fixup.py` restores them now, along with the engine sequence in the pending-tally
diagnostic, which counts internal change batches and is not a fact a transcript should
hold.
The script now keeps the promise its own docstring makes, that `golden-update` is a
single reviewable step.

### D5 — A timing gate was measuring the machine

`test_active_tracker_event_loop_stall` failed on CI at 71 ms against a 50 ms budget, on
all three Python versions, while the identical source measured 3-5 ms locally.

An absolute millisecond budget measures the machine as much as the code.
Taking the best of three attempts narrowed the spread but did not change what was being
measured, and CI failed again at 61 ms on a runner where `_tick` was doing nothing but
waiting on its executor.

A slower machine inflates the stall and inflates the tick’s wall time with it, so the
share between them is the part a machine cannot fake.
The gate is that share now, above an absolute floor below which the loop is simply not
blocked.

The separation is not close.
Clean, the loop is blocked for 0.7% of the tick; with the regression it guards --
`poll_observations` and `_compute_updates` called on the loop rather than through
`asyncio.to_thread` -- the stall *is* the tick, at 49.8%. The threshold sits at 25%, and
the contended CI runs that prompted this would have measured about 6%. Both directions
were verified before the change was committed.

`test_simultaneous_identical_rollups_compute_once` is the same class and is left alone
for now, tracked as `mb-rfot`: it failed once in four full-suite runs and passes in
isolation every time.
It asserts that six concurrent rollups coalesce to one build, which a version advancing
mid-gather can legitimately split into two.

## What is strong

These are the parts a native provider will lean on.

**The handle is small and batched.** Five methods; `read` takes many queries and returns
one coherent version, cursor, lifecycle state, and work record.
A native binding crosses the boundary once per read, not once per query.

**Bounds are separated rather than conflated.** The discovery budget, per-page row
bound, aggregate query bound, lifecycle issue bound, and read-bundle bound are distinct.
Conflating them is the usual way a boundary like this becomes unimplementable at scale.

**The lifecycle is a real state machine.** `ALLOWED_PHASE_TRANSITIONS` is total over the
phase set, terminal states are terminal, and a test asserts both.
`ready` distinguishes an open idle handle from `watching`, which requires a live
observer — a distinction a native provider needs and would otherwise have to guess.
The spike found the one place this disagreed with fdu, on resource refusal, and the
stack aligned it.

**Invalidation is resumable with explicit reset.** `changes(after=cursor)` with a typed
gap reset can be implemented over a poll or a channel without an event loop on the far
side.

**Work counters share a vocabulary with the native engine.** Thirteen semantic counters,
timing values that may be absent rather than zero, and a diagnostics record that names
which provider answered.
A comparison across the swap therefore describes the same work rather than two
vocabularies.

**The conformance suite enforces its own integrity.** A meta-test asserts every
registered case is factory-parametrized, so a Python-only test cannot be added to the
registry; another asserts the architecture document lists every case.
The registry is maintained rather than aspirational.

**The coordinator holds no mirror state.** Lifecycle, versioning, a bounded change
history, and subscriber sets — no entry mirror.
Host decorations live in a sparse path-keyed overlay a provider never sees.
This is the rule most refactors of this kind break, and it holds here.

## Open findings

### F1 — The contract returns browser wire models on the aggregate paths

Tracked as `mb-gwlw`. Unchanged by the stack, and now supported by the spike’s
measurements.

`contract.py` has three non-standard-library imports.
One is `metabrowser.wire_models`, the browser’s JSON response layer.

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

The stack’s ownership table puts serialization and browser policy in the route layer.
These payloads are the exception, and they are the exception on precisely the surfaces a
native engine is meant to make fast.

The spike shows the consequence rather than predicting it.
Its adapter had to materialize the complete native projection and run the Python
projection oracle over a temporary image for every read, because the contract asks for a
shape only that oracle produces.
It recorded 8,830 materialized entries and four aggregate passes for one read, and
recommended native filtered-tree and rollup projections to remove them.
That work cannot be removed while the contract’s type for it is the browser’s.

There is a sharp way to see the size of the gap.
`test_protocols_are_structural_and_provider_neutral` already asserts the contract is
provider-neutral by checking its imports against a denylist, which this review updated
to name modules that still exist.
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
parity explicitly. Either way the decision belongs before a second provider lands, and
the spike’s existence makes that soon.

### F3 — No conformance case pins the aggregate payload shape

Tracked as `mb-nqgs`.

The nineteen registered cases cover checkpoints, semantic parity, orders, bounds,
paging, version pins, changes, verified refresh, lifecycle, sessions, and joined close.
None asserts the shape of the rollup and navigation payloads.

Because those payloads are `list[list[object]]` and `list[Any]`, a second provider can
satisfy every registered case and still return rows the browser cannot read: a tally row
with its elements in a different order, seconds where nanoseconds were expected, a
differently nested node.
Nothing in the suite would fail.

The order work makes this sharper rather than softer.
Having made row order total and testable, the shape of what those rows are made of is
now the largest thing left to a reader’s inference.

F1 and F3 are the same problem from two directions.
Fixing F1 makes F3 mostly mechanical, because a typed payload is a payload a conformance
case can assert.

## Testing added

Three files, each confirmed to fail against the code before its fix.

- `test_inventory_path_boundary.py` asserts the property a provider depends on:
  everything `parse_inventory_path` accepts is already canonical by
  `require_canonical_inventory_path`, the translation is idempotent, equivalent
  spellings are indistinguishable at the routes, and no query string can raise out of
  the boundary. It also pins the composition of the two directions, including that a raw
  platform name is a miss rather than a raise.
- `test_inventory_debug_route.py` pins `/_debug/inventory`. Two tools parse that payload
  and nothing asserted it.
  It separates the four keys the benchmarks actually parse from the thirteen semantic
  counters and the four timing values, because those are three different promises — and
  it earned its place immediately by catching `directories_visited` becoming
  `directories_read` during the stack merge.
- A case in `test_catalog_feed_server.py` covers D3 from the direction the existing test
  did not: identity across a change the catalog does not carry.

`/_debug/inventory` also gained the parity row it needed, exempt for the reason
`/_debug/tasks` is: its work counters carry wall and CPU times that no transcript can
pin.

## Before the native provider is written

1. Settle F1. A native binding written against `list[list[object]]` will encode today’s
   positional layout by observation, and that becomes the contract by accident.
   The spike’s fourth recommendation cannot be implemented without it.
2. Settle F2, so every CLI mode names the engine it read.
3. Add F3’s conformance case, so the aggregate shape is pinned for every registered
   backend rather than for the one that happens to build it today.
4. Resolve the journal-capacity question the spike raised: with a capacity of one, one
   refresh can produce several native commits, so the contract needs to define capacity
   and replay in provider-batch terms.
   Resource-stop semantics, the spike’s other finding, are already aligned.
5. Consider giving `CatalogProjection` a content identity.
   D3 was fixed host-side because the contract offers no way for a provider to report
   that a projection did not move.

The spike also names a real open question of its own: the contract path is used as a
filesystem *address* as well as an identity, so `root / path` breaks once the path is
the escaped form. fdu carries both a native path and a canonical one per row.
Deciding which shape to mirror is a contract decision, not an implementation detail, and
it belongs with F1 because both are about what a row is made of.

## Performance

The refactor is behaviour-preserving by intent, and it was measured for that.
It was not measured for speed: every one of the 197 rows in the performance loop’s
recorded runs has a null `inventory_provider`, so no run has ever been taken on the
refactored engine.

A full scan on a 60,000-file synthetic corpus, timed through
`metab CORPUS --api /api/index/meta`, three runs, median:

| Build | Median | Against main |
| --- | --- | --- |
| main | 2,071 ms | — |
| the stack, as its pull requests stood | 5,690 ms | **2.75x slower** |
| the stack, with the two fixes below | 2,652 ms | 1.28x slower |

Both causes are on the per-entry path, and neither was visible in any test.
Both arrive with the bottom of the stack, which matters for merge order: the
invalidation listener and the pathlib validator are
`codex/fdu-backend-alignment-research`, and `codex/inventory-contract-alignment` adds
the surrogate scan on top of the second.
The fixes are at the top of the stack, so the stack has to land as one — merging the
bottom alone ships the regression.

**Validation ran twice per entry through pathlib.** `require_canonical_inventory_path`
built two `PurePosixPath` objects and asked each for `as_posix()` and `parts`, and —
once the alignment branch added the surrogate refusal — also scanned every character of
every path in a Python-level generator.
It runs once for an entry’s path and once for its parent, about 248,000 times for 60,000
files. Rewritten against the string, it costs 0.36 us instead of 4.75 us, and entry
construction 1.85 us instead of 10.12 us.
`isascii()` is what does the work: every surrogate is non-ASCII, so an ASCII path cannot
hold one and the expensive scan never runs.
The rewrite was checked against the original over 10,180 inputs under both `allow_root`
settings and agrees on every verdict and every message.

**Discovery invalidated caches that were empty.** The host’s projection-invalidation
listener was registered on the coordinator, which publishes every entry it discovers, so
a first walk invalidated once per entry — and each of those resolves the path, a
syscall, once per projection cache.
That is 45,516 resolves for 22,758 entries.
Before the provider boundary this code was reachable only from the watcher, meaning only
when a real change had been seen.
Skipping discovery is safe rather than merely cheap: the caches are mtime keyed and
revalidate on read, so a stale entry is a miss and never a wrong answer.

Walk-to-settled on this repository, five runs: 2,640 ms to 1,117 ms median.

A 28% gap against main remains, tracked as `mb-kicj`. Its profile points at the double
representation: each entry is built as a contract `InventoryEntry`, converted to the
provider’s retained `FsEntry`, mutated one to three times with `dataclasses.replace` in
the walker, and converted back on read — 64,420 `replace` calls, 1.28M `getattr`, and
125,525 generated `__init__` calls for 60,000 files.
That is F1 again, measured from a third direction.

## One repository fault, found on the way

The pre-push gate had not been running in any worktree, and `git status` failed in
several of them. `extensions.worktreeConfig` is enabled here, which means `core.bare`
must live in the main worktree’s `config.worktree` rather than the shared config --
git’s own documentation says to move it when enabling the extension, and it had not been
moved. The shared `bare = true` therefore applied to every linked worktree, so git
refused every operation needing a work tree, Lefthook among them.

`core.bare` now sits in the main worktree’s `config.worktree` and is absent from the
shared config, which is the documented layout.
All thirteen live worktrees work, the pre-push gate runs again, and two
`tests/test_public_hygiene.py` failures that looked like defects turn out to have been
`git check-ignore` refusing to run and the scan falling back to a full pass.
Two worktrees whose directories were already gone were pruned.

## Validation

`make verify` passes at every level of the stack, each run on that branch’s own tree:

| Level | Pytest cases |
| --- | --- |
| `codex/fdu-backend-alignment-research` | 1,817 |
| `codex/fdu-opened-root-e2e-spike` | 1,830 |
| `codex/inventory-contract-alignment` | 1,837 |

Each run also covers 99 golden scenarios, lint, type checks, public hygiene, parity (26
covered, 5 exempt), supply-chain audits, and distribution inspection.

## References

- [Inventory provider contract](../architecture/arch-inventory-provider.md)
- [Views, models, and routes](../architecture/arch-views-models-routes.md)
- [Phase 1 refactor and fdu adoption plan](../specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md)
- [fdu and Metabrowser inventory-engine alignment](../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md)
- [fdu inventory adapter spike](../../../explorations/fdu-inventory-adapter/README.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
