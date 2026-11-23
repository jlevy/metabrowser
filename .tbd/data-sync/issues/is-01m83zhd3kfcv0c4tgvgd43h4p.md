---
type: is
id: is-01m83zhd3kfcv0c4tgvgd43h4p
title: "PR #737 B1: the speculative share is first come, first served, and a cold catalog's cores walk can spend it before the prefetch asks"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T10:34:29.361Z
updated_at: 2026-11-23T11:15:45.657Z
started_at: 2026-11-23T10:36:20.298Z
closed_at: 2026-11-23T11:15:45.655Z
close_reason: "Fixed in 267e15c30 on PR #737: CATALOG_SPECULATIVE_CORE_PER_HOUR (8) holds the cores walk and backfill to the share less the prefetch's priced 92; store-given files lists skip the governor. B2-B4 fixed in b12414301, 27f227f27, 267e15c30. Dispositions: https://github.com/jlevy/metabrowser/pull/737#issuecomment-7099325542"
resolution: null
duplicate_of: null
---
Review: https://github.com/jlevy/metabrowser/pull/737#pullrequestreview-6020063868

SPECULATIVE_CORE_PER_HOUR (100, gh_budget.py) is one first-come share for the prefetch, backfill, cores walk, and labels. A cold catalog's walk (batches of 8, one GraphQL point each) of 800 rows spends all 100; the prefetch is then refused with self_ceiling, files lists the store gives at no GitHub cost included (_files asks _governor before it checks local). Fix: order the share or give the walk its own number; let a store-given files list past the share; update the plan's 'is unchanged' (line 215); pin with a test where the walk spends first; record one cold first visit's governor.ceiling beside the constant.
