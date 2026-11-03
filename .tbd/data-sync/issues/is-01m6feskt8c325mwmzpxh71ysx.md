---
type: is
id: is-01m6feskt8c325mwmzpxh71ysx
title: "PR #283 C1: a boundary commit comparison is computed against the empty tree and shown as its diff"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
hold: null
hold_until: null
created_at: 2026-11-03T01:01:22.119Z
updated_at: 2026-11-03T01:54:03.366Z
started_at: 2026-11-03T01:33:06.247Z
closed_at: 2026-11-03T01:54:03.365Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: C1 boundary commit diff refused as parent_unavailable; commit stats unknown; CHANGELOG"
resolution: null
duplicate_of: null
---
High. Review C https://github.com/jlevy/metabrowser/pull/283#pullrequestreview-5745516755. diff/adapters/git.py:143-149; git/detail.py parent_ids. Shared by a shallow folder.
