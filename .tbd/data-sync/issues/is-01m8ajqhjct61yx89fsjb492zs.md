---
type: is
id: is-01m8ajqhjct61yx89fsjb492zs
title: Pin the upstream Lean 4 grammar as a fixture and test the port against it
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-25-lean-language-support.md
labels: []
dependencies: []
parent_id: is-01m8ahev7t0174z3a2vhhnpw81
created_at: 2026-11-26T00:05:20.076Z
updated_at: 2026-11-26T00:05:20.076Z
---
Copy lean4.json at a recorded vscode-lean4 commit, with its Apache-2.0 LICENSE, under tests/fixtures/vscode-lean4/. A test asserts every upstream rule regex appears verbatim in the port's table, so refreshing the fixture fails until the port follows it.
