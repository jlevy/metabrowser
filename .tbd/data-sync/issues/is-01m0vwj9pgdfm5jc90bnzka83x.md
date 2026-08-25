---
type: is
id: is-01m0vwj9pgdfm5jc90bnzka83x
title: "PR #74 review 74-1: remove read-path overlay validation and use real tree page bounds"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:44.686Z
updated_at: 2026-08-25T07:58:57.523Z
closed_at: 2026-08-25T07:58:57.522Z
close_reason: "Fixed: overlay canonical validation now occurs on writes only, and route/event tree assembly uses a dedicated bounded provider page size rather than the discovery budget."
resolution: null
duplicate_of: null
---
Review 5406736360. overlay.py:110-120 and server.py tree assembly: validate host decoration paths on replace/replace_many only; provider output is canonical by contract and conformance test. Give /api/tree a measured per-page row bound instead of max_files, preserving lossless version-pinned assembly.
