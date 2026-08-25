---
type: is
id: is-01m0vwjendrserxszvhwbgmw2z
title: "PR #74 review 74-6: type rollup and navigation projection payloads"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:49.771Z
updated_at: 2026-08-25T07:58:58.992Z
closed_at: 2026-08-25T07:58:58.991Z
close_reason: "Fixed: rollup and navigation projections use named typed payloads with exact golden-shape validation."
resolution: null
duplicate_of: null
---
Review 5406736360. contract.py RollupProjection and NavigationProjection expose Mapping[str, object]. Replace them with frozen typed records covering File Rollup Format and navigation tally shapes, with provider harness coverage.
