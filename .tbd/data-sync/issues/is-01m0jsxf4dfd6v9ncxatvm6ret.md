---
type: is
id: is-01m0jsxf4dfd6v9ncxatvm6ret
title: Goldens for /api/rollup, including truncated and pending subtrees
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:39:15.084Z
updated_at: 2026-08-30T00:56:27.915Z
closed_at: 2026-08-30T00:56:27.914Z
close_reason: Pinned by cli-api-nav.tryscript.md and cli-api-plugins.tryscript.md via metab --api. Rollup truncation is explicitly out of reach of a sandbox fixture and noted in the golden; mb-crmq's remainder is recorded there.
resolution: null
duplicate_of: null
---
The rollup feeds both folder views, Overview and Treemap. Cover a complete subtree, one truncated by the node budget (children retained alongside a rest bucket), and one still pending while the walk converges, since the client renders those three states differently.
