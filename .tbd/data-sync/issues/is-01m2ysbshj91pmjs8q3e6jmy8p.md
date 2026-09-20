---
type: is
id: is-01m2ysbshj91pmjs8q3e6jmy8p
title: "PR 216 R1: resolve repeated subtree objects under each parent path"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2yryd6had8zdvj8eag4a4v4
hold: null
hold_until: null
created_at: 2026-09-20T06:51:52.750Z
updated_at: 2026-09-20T07:15:19.204Z
started_at: 2026-09-20T06:53:08.702Z
closed_at: 2026-09-20T07:15:19.203Z
close_reason: "Fixed in bc8dd72b: _list_tree_oid reparents cached tree entries under the lookup path."
resolution: null
duplicate_of: null
---
src/metabrowser/git/tree_source.py:773 caches path-bearing entries solely by tree OID. Reproduced one/file.txt resolving then identical two/file.txt returning None. Reparent cached entries and cover alternating reads.
