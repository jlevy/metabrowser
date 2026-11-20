---
type: is
id: is-01m7v72dn5j2b1v6gqgsr8ynvx
title: "Flake on main: ref selector long-list Chrome test loses the End row (test_ref_selector_long_list_chrome)"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T00:52:57.123Z
updated_at: 2026-11-20T00:52:57.123Z
---
Failed on main run 44646591465 (End focused (None, None) != (2001, 'b-0000')) and on PR #619 run 44647974385 (end inView False). Docs-only PR, so a timing flake in the test or the virtualized list's End handling.
