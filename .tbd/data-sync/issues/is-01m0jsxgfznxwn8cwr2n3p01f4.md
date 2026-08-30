---
type: is
id: is-01m0jsxgfznxwn8cwr2n3p01f4
title: Extend --show to resolve /commit and container inner paths
kind: feature
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:39:16.478Z
updated_at: 2026-08-30T02:31:24.719Z
closed_at: 2026-08-30T02:31:24.718Z
close_reason: --show resolves /view/<path>, /view/<container>/<inner>, /commit/<rev>, and /commit/<rev>/<inner>, reusing the server's own route decoders and view registry. Pinned in cli-show and cli-api-git; malformed revisions refused.
resolution: null
duplicate_of: null
---
The browser URL grammar — /view/<container>/<inner>, /commit/<rev>, /commit/<rev>/<inner>, and the _mb_ query reservation — is tested only in Python units and one DOM suite, never end to end. Resolving them through --show gives the grammar its first transcript coverage and exercises the container contract in one command.
