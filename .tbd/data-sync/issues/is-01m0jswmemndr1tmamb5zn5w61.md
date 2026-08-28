---
type: is
id: is-01m0jswmemndr1tmamb5zn5w61
title: Shared in-process ASGI client and a stated session schema
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0jswmscrn01e2avbk6g8w1h
  - type: blocks
    target: is-01m0jswn4dgygrcgnzz5g2mbtj
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:38:47.763Z
updated_at: 2026-08-28T06:48:57.859Z
closed_at: 2026-08-28T06:48:57.850Z
close_reason: Shared InProcessClient (with POST, query-in-path, headers, and caller label/logger) lifted to cli/asgi_client.py; normalize.py adds the stated session schema with an evidence-based field table. Every existing golden byte-identical; 1628 tests pass.
resolution: null
duplicate_of: null
---
Lift _InProcessClient out of cli/check_api.py so a second mode can drive the real request stack, and add metabrowser/normalize.py: one table naming every unstable field and what replaces it (served-root paths, mtimes, git revisions, elapsed times). The golden-testing guidance asks for exactly this and today each transcript solves it locally, with touch -t in one fixture and a regex in another. A general-purpose --api mode is not diffable without it.
