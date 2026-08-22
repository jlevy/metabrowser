---
type: is
id: is-01m0nvgrn9vcdqqtchgf2mhxzv
title: "PR #66 review F2: worker-thread index read is unlocked and skews revision"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01m0nvgqxqbb35etfxh3xbbkh9
created_at: 2026-08-22T23:04:59.305Z
updated_at: 2026-08-22T23:07:23.726Z
closed_at: 2026-08-22T23:07:23.725Z
close_reason: "Fixed: navigation_tallies_snapshotting takes _rollup_cache_lock and reads entries and revision inside one acquisition, closing both the unlocked-read and the skew. arch-state-and-delivery.md updated with the worker-thread carve-out. Test test_the_snapshot_and_its_revision_are_read_together pins it."
---
inventory.py:652 via server.py to_thread. navigation_tallies_snapshotting is the first call site to read _entries FROM a worker thread; writers _replace_index_entry/_pop_index_entry hold _rollup_cache_lock. Two consequences: (a) unlocked read, benign under the GIL today but breaks on free-threaded builds and CI runs 3.14; (b) snapshot and revision are NOT taken atomically, so the memo can be keyed to a revision newer than the contents it summarizes — if that lands on the walk's final writes the settled tree serves under-counted tallies indefinitely. Fix: one _rollup_cache_lock acquisition covering both reads. Also update arch-state-and-delivery.md:79-90, whose lock-free invariant this violates.
