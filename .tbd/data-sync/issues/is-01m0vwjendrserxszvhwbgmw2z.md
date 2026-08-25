---
type: is
id: is-01m0vwjendrserxszvhwbgmw2z
title: "PR #74 review 74-6: type rollup and navigation projection payloads"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:49.771Z
updated_at: 2026-08-25T07:18:49.771Z
---
Review 5406736360. contract.py RollupProjection and NavigationProjection expose Mapping[str, object]. Replace them with frozen typed records covering File Rollup Format and navigation tally shapes, with provider harness coverage.
