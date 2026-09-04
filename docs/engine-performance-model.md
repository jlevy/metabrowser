# Engine Performance Model

**Status:** Approved

## Purpose

Metabrowser opens whatever directory it is pointed at, and the trees people actually
open hold hundreds of thousands of entries.
Everything the engine does once per entry is therefore multiplied by a number nobody
chose, and at that multiplier a microsecond is a real quantity: at 300,000 entries, one
microsecond per entry is 0.3 seconds.

This document is the engine-agnostic half of that subject — the rule about what may run
on the multiplied path, what a boundary costs when it is crossed per entry, and which
instruments can be trusted to tell you.
It holds for any implementation behind
[the inventory provider contract](project/architecture/arch-inventory-provider.md),
including a native one.

The measured cost of a particular engine is not here, because it does not survive
replacing that engine.
Each implementation documents its own unit costs and its own residue:

| Engine | Costs |
| --- | --- |
| Python reference provider | [Python inventory cost](project/architecture/arch-python-inventory-cost.md) |

This is the backend counterpart to the
[Web Performance Framework](web-performance-framework.md), which measures what a reader
sees, and it shares its evidence discipline.
It is the same measure-before-you-bound rule that
[Rendering Large Content](large-content-rendering.md) applies to a single file, applied
instead to the number of files.

## The Per-Entry Rule

**Nothing goes on the per-entry path without a measured reason.**

The per-entry path is everything between the filesystem naming an entry and the engine
retaining a record for it.
It is not the place for validation that could happen once at a boundary, for a
conversion that exists to satisfy a type, or for publishing a change no reader has seen.
Each of those is defensible in isolation, and none survives being multiplied by the size
of a real tree.

Three consequences are worth stating, because they are the ones that get argued:

**The filesystem work is usually not the problem.** Two engines walking the same tree
issue the same directory reads and stats.
When one is slower and the syscall counts match, the difference is in the language
runtime, and it is on this path.
Counting the syscalls first is what stops a CPU problem from being investigated as an
I/O problem.

**A boundary crossed per entry is a boundary in the hot path.** Provider contracts exist
to be crossed by *queries*, which are few, not by every discovered entry, which are
many. An engine that constructs the contract’s types per entry has moved a boundary cost
onto the multiplied path, whatever the boundary was designed for.
The rule is that the walker produces what the engine retains; conversion happens where
results cross out, in proportion to what is read rather than to what exists.

**A layering rule will be satisfied by whatever route is available.** An import ban is a
statement about dependency, not about cost, and the cheapest way to satisfy one is not
always the way taken — routing a hot path through a validating type to avoid naming a
record is a real way to obey the letter of such a rule.
When the honest answer is that a type belongs to neither side of the boundary, move it
to a module that belongs to neither.
See
[the Python engine’s history](project/architecture/arch-python-inventory-cost.md#what-the-boundary-cost-once)
for the worked case.

## Measurement Discipline

Every rule here was learned by being misled by its absence.

**Counts before times.** A count is deterministic: the same under any load, on any host,
in any order. Two engines walking the same corpus should produce the same counts, and
where they differ, that difference is the finding — contention can neither hide nor
manufacture it. Reach for wall-clock to confirm a count-level result, not to discover
one.

**A run that did not finish is not a slower run.** A harness that times a process and
checks its exit status will happily compare a build that walked the whole tree against
one that gave up partway, and report the second as merely somewhat slower.
Any comparison must read back how much work was actually done — entries indexed,
completion state — and refuse to report when the runs do not match.

**A live tree is not a corpus.** A working tree that something else is writing to
changes between runs, and one sharing a host with other heavy work is not measuring what
you think. Real trees are still worth using, because their directory shapes and depth
distributions are ones no generator produces; but record the load and the entry count
next to the number, and treat a synthetic corpus as the thing you iterate against.

**Deterministic profilers overstate high-call-count functions.** Per-call
instrumentation overhead lands hardest exactly where the calls are most numerous, which
on this path is everywhere that matters.
Use such a profile to find *where*, then price the candidates in isolation.

**Order and warmup are part of the measurement.** Running every trial of one build and
then every trial of the other charges all drift to whichever went second.
Interleaving fixes that; a fixed within-pass order still leaves page-cache and
processor-ramp effects attached to the label, so passes alternate.
The first touch of a tree pays for the cache every later run enjoys, so a warmup pass is
timed and discarded.

**Record what was compared.** A mode whose purpose is comparing builds has to be able to
say which builds — commit and clean-or-dirty — and has to mark profiled runs so they are
never later quoted as measurements.

## Where This Is Implemented

`explorations/performance-loop/scan_bench.py` is the engine bench: an in-process mode
for iterating a per-entry change and an interleaved build-against-build mode for a claim
against another build.
It enforces the completeness and equal-work checks above.
Neither mode is a release gate; `explorations/performance-loop/run.py` owns that, and
`devtools/bench_serving.py` owns serving measurement inside `make verify`.

## References

- [Inventory provider contract](project/architecture/arch-inventory-provider.md) — the
  boundary this model says not to cross per entry
- [Python inventory cost](project/architecture/arch-python-inventory-cost.md) — the
  reference engine’s measured unit costs
- [Web Performance Framework](web-performance-framework.md) — the browser half
- [Rendering Large Content](large-content-rendering.md) — the same rule for one large
  file
- [Load-time explorations](../explorations/performance-loop/README.md) — the loop, the
  corpora, and the experiment records

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
