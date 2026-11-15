# Engine Performance Model

**Status:** Approved standard.
It applies to every inventory engine behind the provider contract; the Python reference
provider is the one built today.

## Purpose

Metabrowser opens whatever directory it is pointed at, and the trees people open hold
hundreds of thousands of entries.
Everything the engine does once per entry is multiplied by a number nobody chose, and at
that multiplier a microsecond is a real quantity: at 300,000 entries, one microsecond
per entry is 0.3 seconds.

This standard is the engine-independent half of that subject: what may run on the
multiplied path, and what a boundary costs when it is crossed per entry.
It holds for any implementation behind
[the inventory provider contract](project/architecture/arch-inventory-provider.md),
including a native one.
An engine’s measured unit costs do not survive replacing it, so each engine documents
its own: the Python reference provider’s are in
[the Python inventory engine](project/architecture/arch-inventory-engine-python.md).

It is the backend counterpart to the
[Web Performance Framework](web-performance-framework.md), which measures what a reader
sees, and the same measure-before-you-bound rule that
[Rendering Large Content](large-content-rendering.md) applies to one file, applied to
the number of files.
How to measure a claim under it is in
[Benchmarking Scan and Serve](development.md#benchmarking-scan-and-serve).

## The Per-Entry Rule

**Nothing goes on the per-entry path without a measured reason.**

The per-entry path is everything between the filesystem naming an entry and the engine
retaining a record for it.
It is not the place for validation that could happen once at a boundary, for a
conversion that exists to satisfy a type, or for publishing a change no reader has seen.
Each of those is defensible in isolation, and none survives being multiplied by the size
of a real tree.

Three consequences are the ones that get argued:

**The filesystem work is usually not the problem.** Two engines walking the same tree
issue the same directory reads and stats.
When one is slower and the syscall counts match, the difference is in the language
runtime, on this path.
Counting the syscalls first stops a CPU problem from being investigated as an I/O
problem.

**A boundary crossed per entry is a boundary in the hot path.** Provider contracts are
crossed by queries, which are few, not by every discovered entry, which are many.
An engine that constructs the contract’s types per entry has moved a boundary cost onto
the multiplied path, whatever the boundary was designed for.
The walker produces what the engine retains, and conversion happens where results cross
out, in proportion to what is read rather than to what exists.

**A layering rule will be satisfied by whatever route is available.** An import ban is a
statement about dependency, not cost, and routing a hot path through a validating type
to avoid naming a record obeys the letter of such a rule.
When a type belongs to neither side of a boundary, move it to a module that belongs to
neither. The Python engine’s document has the worked case.

## References

- [Inventory provider contract](project/architecture/arch-inventory-provider.md): the
  boundary this model says not to cross per entry
- [Python inventory engine](project/architecture/arch-inventory-engine-python.md): the
  reference engine’s unit costs
- [Benchmarking Scan and Serve](development.md#benchmarking-scan-and-serve): the
  measurement discipline and the harnesses
- [Load-time explorations](../explorations/performance-loop/README.md): the loop, the
  corpora, and the experiment records

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
