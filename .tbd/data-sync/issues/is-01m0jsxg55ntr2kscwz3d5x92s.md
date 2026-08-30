---
type: is
id: is-01m0jsxg55ntr2kscwz3d5x92s
title: Goldens for /api/recent and /api/activity
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:39:16.132Z
updated_at: 2026-08-30T00:56:27.924Z
closed_at: 2026-08-30T00:56:27.924Z
close_reason: Pinned by cli-api-nav.tryscript.md and cli-api-plugins.tryscript.md via metab --api. Rollup truncation is explicitly out of reach of a sandbox fixture and noted in the golden; mb-crmq's remainder is recorded there.
resolution: null
duplicate_of: null
---
--check-api reports a recent count and nothing else, so nothing pins the clustered rows the recency source actually returns. /api/activity has no coverage at all. Both need pinned mtimes in the fixture to be deterministic.
