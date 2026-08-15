---
type: is
id: is-01m023cq7qajqd0y3x4r4378sv
title: "Binary preview: documentation, manual checklist, and verify gate"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/done/plan-2026-08-11-binary-byte-preview.md
labels: []
dependencies: []
parent_id: is-01kzt2pwbyj3rt7y2xhevg8ff5
created_at: 2026-08-15T06:57:46.743Z
updated_at: 2026-08-15T07:29:01.587Z
closed_at: 2026-08-15T07:29:01.587Z
close_reason: null
---
Close out the feature.

## `docs/plugins.md`

Note that a built-in plugin may own a bounded chunked data hook, using
`/api/plugin/binary/chunk` as the worked example. Keep it short and link to the
plan rather than restating the byte contract.

## `docs/e2e-testing.md`

The manual browser checklist already names the binary view. Extend it to cover
loading a second chunk and the oversize state, and confirm no horizontal
overflow at narrow and wide panes in both themes.

## Plan document

Move `plan-2026-08-11-binary-byte-preview.md` from `specs/active/` to
`specs/done/` and move its entry in `docs/project/README.md` from Active Feature
Plans to Done Plans once the feature ships. Update `TODO.md` if it tracks this
work.

## Gate

Run `make format`, then `make verify` (formatting, Python and browser lint, type
checks, public-hygiene, tests, locked Python and npm audits, distribution
inspection, isolated installed-wheel smoke tests). Run
`uv --config-file uv.toml run --frozen python devtools/public_hygiene.py`.
Close the beads, run `tbd sync`, commit, push, and watch CI to completion.
