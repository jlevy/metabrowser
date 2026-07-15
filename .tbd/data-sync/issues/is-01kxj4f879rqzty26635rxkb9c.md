---
type: is
id: is-01kxj4f879rqzty26635rxkb9c
title: "PR #1 final audit: document the bare-path CLI shorthand"
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T05:37:23.688Z
updated_at: 2026-07-15T06:02:32.748Z
closed_at: 2026-07-15T06:02:32.748Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
The portable skill tells agents to pass a path directly, but metab --help lists only subcommands and does not expose the canonical metab PATH shorthand implemented by argv rewriting. Add a stable help example for metab PATH and metab serve PATH, plus a CLI contract regression.

## Notes

Top-level CLI help now documents metab PATH, metab serve PATH --no-open, and plugin help examples. CLI help regression passes.
