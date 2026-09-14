---
type: is
id: is-01m2f0m2t7ts1q612cjz1fhy5p
title: "PR #115 review S1-S5: Non-blocking suggestions (walk_elapsed_ms ownership, uv venv config, build --clear, marker tests, env pinning)"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2f0m0sdxg3fe8v091zxkby8
created_at: 2026-09-14T03:50:53.511Z
updated_at: 2026-09-14T04:48:11.457Z
closed_at: 2026-09-14T04:48:11.456Z
close_reason: "Fixed in bbd16783: S1 payload filter for server-reported keys, S2 uv --config-file venv, S3 --clear, S4 marker tests for removal/replacement/below-root, S5 constraints exported from uv.lock"
resolution: null
duplicate_of: null
---
PR #115 review suggestions S1-S5 (non-blocking).

- S1: run.py:1148-1175 run = {**payload, ..., **walk_facts} keeps a pasted walk_elapsed_ms when the walk falls back to the progress route; the harness should own it (null when unlogged).
- S2: use uv --config-file uv.toml venv in the README recipes (docs/development.md: machine-global uv config merges into direct invocations).
- S3: add --clear to uv build --out-dir so the ls glob cannot match two wheels on a rerun.
- S4: _corpus_launch_marker tests: add cases for removing a top-level entry and for replacing the root.
- S5: consider pinning the shared environment's dependencies to constraints exported from the candidate's uv.lock.
