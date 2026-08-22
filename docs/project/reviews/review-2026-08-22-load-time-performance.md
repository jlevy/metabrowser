# Review: Load-Time Performance and the Distance Still to Cover

**Date:** 2026-08-22

**Author:** Metabrowser maintainers

**Status:** Complete.
Reviews branch `claude/perf-subtree-sweep` at `4e666ea` against `main` at `512e70b`. The
findings describe that branch; the principles and candidate hypotheses are proposals,
not decisions.

**Scope:** The full branch diff, 39 files, read as whole functions rather than as hunks,
with the branch checked out and every number below reproduced locally.

## Executive Summary

The branch is sound and mergeable.
Six rounds of measured work took dead time before the first row from 21.4 s to 2.2 s on
a 241,000-file working tree, a navigation request during a scan from 777 ms to 6 ms, and
the attached scan from 258 s to 50 s. The one semantic change, gitignore pre-walk
pruning, is verified by comparison against the unpruned filter rather than by argument.
Eight findings follow and none of them block.

The measurement discipline is the more durable contribution.
Naming the metric before measuring, refusing a median without its range, sizing n to the
effect, and writing up the two rejected rounds as fully as the wins are the reasons
these numbers can be trusted.
Two gaps in that discipline are worth closing, and they are in
[Where the Loop Cannot See](#where-the-loop-cannot-see).

The rest of this document is about what the six rounds did not attempt.
Each round removed a cost from an architecture that was held fixed.
Three properties of that architecture set the current floor, and none of them was in
scope: the index is rebuilt from scratch every session, the walk is sequential
interpreted code, and reads are passes over the whole index.
Every remaining order-of-magnitude change comes from reversing one of those.

## What Was Verified

| Check | Result |
| --- | --- |
| GitHub checks | 5 of 5 green: lint, distribution, tests on 3.12, 3.13, 3.14 |
| `make verify` locally | Exit 0 |
| Python tests | 1,421 passed |
| Browser tests | 48 passed |

Two environment notes, both pre-existing on `main` and unrelated to the branch:
`uv.toml` requires uv 0.11.26 or newer, and `package.json` requires Node 24.18.0 or
newer. A container below either fails `make install` before reaching any project code.

## Findings

None block the merge.
F1 and F2 are the two worth fixing first, and both are small.

| ID | Severity | Subject |
| --- | --- | --- |
| F1 | Medium | The tally fast path goes dead once the tree settles |
| F2 | Medium | A new cross-thread index read runs without the writers’ lock |
| F3 | Low-Medium | The prune’s safety argument rests on a separate pre-existing bug |
| F4 | Low | `navigation_tallies_fresh_within` docstring names a parameter that does not exist |
| F5 | Low | Empty `pass` branch used as control flow in `api_tree` |
| F6 | Low | Inlined rows are stranded when the tree fetch throws rather than returning non-OK |
| F7 | Low | `_git_ignored` re-spawns an invariant git call, now once per directory |
| F8 | Low | `_build_inventory_tree` builds the whole root level, then truncates to 200 |

### F1: The Tally Fast Path Goes Dead Once the Tree Settles

`inventory.py:582`, `inventory.py:586-636`, `inventory.py:638-660`

`_navigation_tally_at` is written only in the recompute branch.
A memo *hit* never refreshes it, so once the walk finishes and the revision stops
moving, the memo ages past its bound and `navigation_tallies_fresh_within` misses
permanently. The route then falls through to `navigation_tallies_snapshotting`, which
copies the whole index before `navigation_tallies` discovers the revision is unchanged
and returns the memo, at which point the copy is discarded.

Measured against a 200,000-entry index with the revision frozen, each subsequent
`depth=0` poll copied 200,000 entries in 5.2 to 5.8 ms and threw the copy away, with the
memo age growing without bound.
The nav polls about once a second per open tab, so this is steady-state waste that
scales linearly with the index, and it is the cost `navigation_tallies_fresh_within` was
introduced to avoid.

When the revision is unchanged the memo is provably current, so age should not gate it.
Return the memo whenever `memo_key[0] == self.rollup_revision()`, which costs a lock and
an integer read, and apply the age bound only when the revision has moved.
The bound is a concession to a moving revision and should not apply to a still one.

### F2: A New Cross-Thread Index Read Runs Without the Writers’ Lock

`inventory.py:652` reached from `server.py:1531-1536`; read path `inventory.py:446`;
writers `inventory.py:951-975`, both under `_rollup_cache_lock`

On `main` every `entries()` call ran on the event loop and only the resulting snapshot
crossed into a thread.
`navigation_tallies_snapshotting` is the first call site to read the index *from* a
worker thread; every `entries()` call site on both branches was checked to confirm this.

The unlocked read is not a crash today.
`list(dict.values())` is effectively atomic under the GIL, confirmed with 62 concurrent
snapshots against 200,000 insertions and zero `RuntimeError`. The writers’ lock is now
doing nothing for this reader, which is the pattern that stops working on a
free-threaded build, and CI already runs 3.14.

The second consequence does bite today.
`snapshot = self.entries(...)` runs, then `revision=self.rollup_revision()` is evaluated
after it, so the walker can write in between and the memo can be keyed to a revision
newer than the contents it summarizes.
If that lands on the walk’s final writes, the settled tree serves under-counted tallies
from that memo indefinitely, because the revision never advances again to evict it.
The window is narrow and the consequence is persistent.

One lock acquisition covering both reads closes the race and the skew together, and
costs nothing that is not already paid.

`arch-state-and-delivery.md` justifies lock-free index access on the grounds that no
other producer can interleave inside a region containing no `await`. A worker thread is
exactly such a producer, so whichever way F2 is resolved, that paragraph needs a
sentence about worker threads.

### F3: The Prune’s Safety Argument Rests on a Pre-Existing Bug

`ignore_filter.py:138-146`, `ignore_filter.py:174`

The comment argues that a spec with fewer patterns matches fewer paths, so a lagging
prune spec prunes less than it could and never prunes something a current one would have
kept. That monotonicity holds only if no negation patterns can enter the accumulated set
during the walk. None can, but only because nested patterns are prefixed as
`f"{rel_dir}/{stripped}"`, which turns `!keep.log` into the literal `pkg/!keep.log`
rather than the negation `!pkg/keep.log`.

The underlying mismatch is pre-existing on `main` and untouched by this branch.
With root `*.log` and `pkg/.gitignore` containing `!keep.log`, `load_gitignore` reports
`pkg/keep.log` as ignored and `git check-ignore` reports it as not ignored.

So this is neither a regression nor a blocker.
It matters because the branch makes the mangling load-bearing: the same pattern set now
decides whether to descend at all.
When someone fixes the prefixing, and it should be fixed, the lag becomes unsound and
the failure mode escalates from one wrong verdict on one file to a whole subtree’s rules
never being read. Name the dependency in the comment, or make it enforceable by
rebuilding eagerly whenever an accumulated line begins with `!`, which costs nothing
today because no such line can exist.

### F4 Through F8

- **F4** — `inventory.py:595` describes tallies “younger than `max_stale_s`” but the
  parameter at `inventory.py:592` is `min_stale_s`, a floor on a derived bound rather
  than a maximum. The two names read as opposites.
- **F5** — `server.py:1513-1514` uses `if ...: pass` followed by two `elif` arms.
  Inverting to a positive guard around the two real branches says the same thing without
  the dead arm.
- **F6** — `app.js:788-800` handles `!resp.ok` by replacing the pane with an error, but
  a network failure or a `resp.json()` parse error throws and is not caught.
  The reader keeps 200 painted rows with no chrome, no counts, no truncation affordance
  and no error: a tree that looks complete and is not.
  Before the inline, the same failure left an empty pane, which reads as broken.
- **F7** — `public_hygiene.py:169` calls `_git_ignored` once per walked directory, and
  each call runs `git rev-parse --local-env-vars` as well as `git check-ignore`. On this
  checkout that is 76 calls over 670 paths in 0.19 s, so it is not a regression here and
  the prune fixes a real non-termination problem.
  The invariant `--local-env-vars` result can be cached at module level, halving the
  spawns.
- **F8** — `server.py:966-978` slices to 200 rows after building the whole root level.
  The cap bounds the bytes on the critical path, which is what the comment argues, but
  not the work: the build is uncapped and synchronous on the event loop for every page
  load. It is index-only with no filesystem access, so it is cheap per row, but a root
  with tens of thousands of immediate children pays all of it per request.

## Checked and Benign

Recording these so the next reader does not re-derive them:

- **The `is_visible` prune cannot drop rules for a directory the shell still shows.**
  `_VISIBLE_HIDDEN` in `fs_paths.py` is `{LOGS_DIR, STATE_DIR}`, the same set
  `make_ignore_filter` exempts through `ALLOWLIST_DIRS`. The two agree, so the prune is
  sound under `IgnoreMode.default`.
- **Inlined rows do not bloat the wire.** `GZipMiddleware` is applied app-wide at
  `minimum_size=1024`, so the shell including the inlined rows is compressed.
- **The scroll listener binds.** Module-scope `getElementById("tree-content")` resolves
  because `app.js` is the last script in `<body>` and the element is earlier in the
  document. It is silently fragile: moving the script to `<head>` or adding `defer` would
  make the optional-chained lookup a no-op and degrade warming to the first screen with
  no error.
- **`compare` already prints `n=` per label**, so the accept rule’s sample-size
  condition is auditable from the table.
- **`_build_inventory_tree` does no filesystem I/O**, so the inline adds no disk reads
  to the render path.
- **Splitting `depth=0` is safe on the wire.** Every tally field is nullable and guarded
  field-by-field on the client, `--check-api` was taught to ask both channels, and
  `CHANGELOG.md` names the user-visible consequence.

## The Distance Still to Cover

Six rounds removed costs from an architecture held fixed.
It is worth stating what the floor would be if the architecture were not fixed, because
the gap is large enough to change what is worth working on.

Three reference points, none of them speculative:

- **ripgrep’s `ignore` crate** walks a tree in parallel with full gitignore semantics,
  compiling patterns into a single matcher rather than looping them per path.
  It is the same job `load_gitignore` and the walker do together.
- **`git status` with fsmonitor and the untracked cache** answers “what is here and what
  changed” on a large working tree in tens of milliseconds, because it consults a change
  journal instead of walking.
- **A cold `stat` sweep of 241,000 files** is roughly one to two seconds single-threaded
  and substantially less in parallel on a warm page cache.
  That is the syscall floor, and it is the only part that is physics.

Against those, 2.2 s of dead time and a 50 s attached scan are not near a limit.
They are the price of three choices:

1. **The index is amnesiac.** It is rebuilt from scratch on every open and discarded on
   exit, so the second open of a tree is priced exactly like the first.
   For a tool used daily on the same few trees, the second open is the common case.
2. **The walk is sequential and interpreted.** One `os.scandir` at a time through
   `asyncio.to_thread`, with pathspec matching that loops patterns in Python for every
   path on the unignored frontier.
3. **Reads are passes over the whole index.** The tally memo, the derived staleness
   bound, the rows-and-tallies split, and the `entries()` snapshot exist to manage the
   cost of a pass that a different representation would make close to free.

The pattern worth noticing across the six rounds is that the wins came from *removing*
work rather than from making work faster, and each round stopped at the boundary of the
architecture. That is the right way to spend a first pass.
It also means the cheap removals are now largely done.

## Principles

Five propositions to test future rounds against.
They are opinions, offered as a way to order work rather than as conclusions.

**Do work proportional to change, not to size.** The tree barely changed since the last
session, so the index should be diffed forward rather than rebuilt.
The same test applies at every layer: a tally should be maintained at write time rather
than recomputed by a pass, the DOM should not re-render proportional to the tree, and
the wire should not recarry what the client already holds.
When a round reaches for a bound, a memo, or a deferral to survive an O(N) cost, the
prior question is whether that cost should exist.
F1 and the whole staleness apparatus are a worked example: they are careful management
of a pass that need not happen.

**Never repeat work across sessions.** This follows from the first but deserves its own
line because nothing in the current design does it at all, and it is the single largest
available change.

**Complete every gesture against local state; let the network reconcile.** Interfaces
that feel effortless are usually not talking to a faster server, they are not talking to
a server on the interaction path.
The hard part is already built: `fs.snapshot` on connect and `fs.change` ops over SSE.
Promoting that from decoration-patching to the primary data path turns fetches into
backfill.

**Count round trips before milliseconds on a remote link.** At 100 ms of latency a 6 ms
response is a 106 ms response, and 32 prefetches are 32 chances to pay it.
In that regime batching and push dominate server-time work.

**Let attention set priority.** exp-002 established this for prefetch by bounding it to
the viewport. The generalization is that the walker should index what the reader is
looking at first. Time until the visible subtree is correct matters more than time to
full scan.

## Where the Loop Cannot See

The accept rule is unusually disciplined.
Three observations about its blind spots.

**The rule grows stricter as evidence accumulates.** The criterion is non-overlapping
ranges at three or more runs per condition, where `_summarize` in `run.py` reports
min-max.
Min-max widens monotonically with n, so collecting more data makes a real effect
harder to confirm. The README’s own example shows the mechanism: exp-003’s band read
342-413 at n=3 and 342-561 at n=6 for the same effect.
A fixed-percentile band or a rank test is stable in n, so more evidence helps rather
than hurts. Keep min-max beside it; it is the honest picture of the tail.

**There is no measured noise floor.** The loop’s hardest lesson, from exp-005, is that a
corpus can match every summary statistic and still be wrong.
An A/A control, the same build recorded under two labels, measures the harness’s own
resolution directly, and `compare` could print it as a reference row so “the ranges do
not overlap” is judged against a known floor.
It costs one extra `serve` and `record` pair per corpus.

**Every measurement is on localhost.** The remote case is a stated deployment target and
a request there costs a fraction of a millisecond in the harness.
No experiment can currently distinguish a design that is fast locally from one that is
fast over a tunnel, and the two orderings differ.

## Candidate Hypotheses

Numbering continues from the registry in
[the load-time plan](../specs/active/plan-2026-08-21-load-time-performance.md), whose
highest registered hypothesis is H32. None of these duplicate that document’s
“Considered and Deliberately Not Registered” section.
Expected magnitudes are predictions to be falsified, not results.

| ID | Hypothesis | Named metric |
| --- | --- | --- |
| H33 | A persisted index makes a revisit cost load-and-verify rather than rescan | Time to first row on a second open of the same tree |
| H34 | Pattern matching, not traversal, dominates what remains of the walk | `walk_elapsed_ms` with and without `gitignore_check` |
| H35 | A native parallel walker collapses the scan by an order of magnitude | `walk_elapsed_ms` on the real tree |
| H36 | On a git tree, git answers the visibility question faster than any walk | Time to a complete visible-set answer |
| H37 | A columnar index makes the tally pass cheap enough to delete its scaffolding | Tally pass duration at 300k and 1M entries |
| H38 | Pushing tallies and deltas removes the poll the staleness bound exists for | Requests per second per tab during and after a scan |
| H39 | A client-side tree replica paints a revisit with no network on the critical path | `first_row_ms` on a revisit, offline |
| H40 | Virtualizing the tree makes interaction latency independent of tree size | Expand, filter, and scroll latency at 10k, 100k, 1M rendered rows |
| H41 | Priority-driven walking makes the visible subtree correct long before the scan ends | Time until the on-screen subtree stops changing |
| H42 | Under realistic latency, batching prefetch beats every server-side win so far | `first_row_ms` and total prefetch time at 0 ms and 120 ms RTT |
| H43 | Serialization is a measurable share of large tree and rollup responses | Server time on `/api/tree` and `/api/rollup` at 300k entries |
| H44 | Bulk-attribute syscalls cut the verification sweep H33 depends on | Verify-sweep duration on an unchanged 241k tree |

### The Ones Worth Explaining

**H33, a persisted index, is the largest single change available.** Serialize the index
periodically and on shutdown.
On start, load it, serve it immediately marked provisional, then verify in the
background: a directory’s mtime changes when its direct children change, so stat only
directories and rescan only subtrees whose mtime moved.
This is the mechanism behind git’s untracked cache.
A revisit becomes load, serve, verify, then push deltas over the SSE channel that
already exists.
It composes with almost everything else here, and it is the only proposal
that changes the common case rather than the first-open case.

**H34 should run before H35 or H36, because it is one run and it decides the order.**
The walker already avoids re-matching inside an ignored subtree, which collapses the
cost to the unignored frontier, but each frontier path still costs a Python-level loop
over the compiled pattern set.
Measuring the walk with and without `gitignore_check` prices that directly.
If matching dominates, H35’s compiled matcher is the fix; if traversal dominates,
parallelism is.

**H35 and H36 are two ways to leave interpreted traversal.** A Rust extension over the
`ignore` crate brings parallelism, single-automaton matching, and correct negation
semantics, which would retire F3’s whole class of bug.
Asking git instead is cheaper to build and applies only to git working trees, which are
plausibly most of the corpus.
They are not exclusive: git for the fast path, native walker for everything else.
The plan already notes that folding the pre-walk into the indexing walk is a larger
change nobody has needed; these are the versions of that change worth doing.

**H37 is the one that deletes code rather than adding it.** Three hundred thousand
`FsEntry` dataclasses are 300,000 heap objects with poor locality, which is why a pass
costs about a second.
Interned path identifiers with parallel arrays for size, mtime, and flags make a tally a
few vectorized operations, with the GIL released inside them.
If it lands, the memo, the derived bound, the rows-and-tallies split, and F1 all become
unnecessary. When a workaround is expensive to reason about, making the underlying
operation cheap is sometimes less total complexity than managing it.

**H39 supersedes exp-004 rather than extending it.** A client replica holds the whole
last-known tree instead of 200 server-rendered rows, paints before the server answers at
all, and reconciles by revision.
It also removes H32’s open question, since a replica does not care whether the server’s
index is warm. With a service worker for the shell, a revisit renders from local storage
with nothing on the network critical path.

**H42 is a measurement change before it is an engineering one.** Add a latency knob to
the harness and record every experiment at 0 ms and roughly 120 ms.
The prediction is that at realistic latency, collapsing 32 prefetch requests into one
batched request outweighs the combined server-side wins of the six rounds.
If that holds, it reorders the backlog.

## Related Documents

- [End-to-end load time, from the CLI to first paint](../specs/active/plan-2026-08-21-load-time-performance.md)
  — the hypothesis registry these candidates extend
- [State and delivery](../architecture/arch-state-and-delivery.md) — the inventory’s
  concurrency model, which F2 touches
- [High-performance file roll-up engine](../research/research-2026-08-06-file-rollup-engine.md)
  — prior art on aggregate representation, relevant to H37

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
