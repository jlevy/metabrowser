---
type: is
id: is-01m1d3qs1c0jthm4v5d93gg0g4
title: metab --walk --stream bypasses the selected inventory provider
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-31T23:51:09.611Z
updated_at: 2026-08-31T23:51:09.611Z
---
walk.py has two paths that disagree about where records come from:

- build_tree_envelope (--walk --all-at-once) reads through the provider: EntryQuery, DirectoryQuery, FilteredTreeQuery.
- stream_dump_lines (--walk --stream) calls metabrowser.walker.walk_tree directly, bypassing the coordinator and the selected backend entirely.

With METABROWSER_INVENTORY_PROVIDER set to a non-Python provider, --walk --stream would still stream the Python walker's records while the server serves the other engine. The CLI would describe an engine that is not the one running, which is the failure the CLI parity rule exists to prevent.

The streaming surface is documented as 'the walker's record sequence', so this may be intentional as a Python-walker debugging tool. If so it should say which engine it reads and be excluded from provider parity explicitly; if not, it needs a bounded streaming read through the contract. Decide before a second provider lands, not after.
