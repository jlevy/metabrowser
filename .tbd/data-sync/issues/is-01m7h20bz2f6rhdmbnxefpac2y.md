---
type: is
id: is-01m7h20bz2f6rhdmbnxefpac2y
title: "PR #449 B2: a listing past the read cap is computed twice before it is refused"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h1z1rnzfafwf740k7yrzdh
hold: null
hold_until: null
created_at: 2026-11-16T02:12:02.657Z
updated_at: 2026-11-16T02:53:18.598Z
started_at: 2026-11-16T02:53:18.265Z
closed_at: 2026-11-16T02:53:18.597Z
close_reason: B2 fixed in 9d7578df6 (overflow stands; cap raised by one read)
resolution: null
duplicate_of: null
---
Severity: Low. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914053530. References: src/metabrowser/diff/adapters/git.py:649-651, :1061-1063. See the review for the full finding and suggested fix.
