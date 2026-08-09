---
type: is
id: is-01kzkv7p0czewd0fzphc929jjr
title: "PR #22 review R8: passive tree observations add gitignored files to a complete catalog"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kzkv76p2eprd181arkqfj0we
created_at: 2026-08-09T18:05:50.987Z
updated_at: 2026-08-09T18:21:04.134Z
closed_at: 2026-08-09T18:21:04.134Z
close_reason: "Fixed in 5f711b8; each has a regression test verified to fail without its fix. make verify green: 783 pytest, 28 golden, both TS configs, hygiene, supply chain, distribution."
---
known_file_catalog.js:5-11 and 96-103. CatalogWireEntry drops gitignored and putEntry() accepts every file from initial/lazy/event snapshots, so ignored rows observed incidentally enter a catalog reported as complete and non-gitignored. Reviewer saw /api/catalog return 6 files while Quick File reported 7 and offered __pycache__/example.pyc. Fix: retain gitignored in the wire typedef, skip/remove ignored entries at passive seams, preserve an ignored path only with explicit navigation provenance, and add a regression for an ignored shallow-tree file plus a complete bulk.
