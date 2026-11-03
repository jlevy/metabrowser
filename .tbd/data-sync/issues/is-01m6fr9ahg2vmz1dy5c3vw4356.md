---
type: is
id: is-01m6fr9ahg2vmz1dy5c3vw4356
title: "PR #284 Qodo (on #283): metab --diff fails on a comparison whose whole patch is past 8 MiB"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fr829v5p0bx9wm4rr3z5wj
hold: null
hold_until: null
created_at: 2026-11-03T03:47:14.095Z
updated_at: 2026-11-03T03:52:31.732Z
started_at: 2026-11-03T03:47:30.645Z
closed_at: 2026-11-03T03:52:31.731Z
close_reason: "fixed in e610ebab: GitDiffSource.hydrate_each asks for each deferred file alone, the CLI projects too_large as the route does, and --diff-check refuses by name; reproduced on a 10.9 MB comparison and pinned by tests/test_cli_diff_bounds.py"
resolution: null
duplicate_of: null
---
High (bot), posted on the layer above: https://github.com/jlevy/metabrowser/pull/283#discussion_r4450564195. src/metabrowser/diff/adapters/git.py file_patches treats a deferred file as an error and src/metabrowser/cli/diff_cli.py asks for every ready file in one run. Reproduced: a 10.9 MB comparison of 3.5 MB files answered 'diff error: file f5 not found in the produced diff' (exit 2) where --api answered the page's document. Fix: GitDiffSource.hydrate_each asks for each deferred file alone; the CLI projects too_large as the page does; --diff-check refuses by name.
