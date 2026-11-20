---
type: is
id: is-01m7paacr9fpsy85e4ktcv30nh
title: metab serve prints Serving before the socket accepts connections
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-18T03:13:31.909Z
updated_at: 2026-11-20T17:01:47.784Z
closed_at: 2026-11-20T17:01:47.764Z
close_reason: Same defect as mb-afxa (Serving printed before the socket accepts); its detail is merged into mb-afxa's notes
resolution: duplicate
duplicate_of: is-01m7rd4zsg2sdmwtz7z1w2z9ws
---
Deferred from PR #541 review A19 (predates that PR): the Serving line can appear before the listening socket accepts, so an agent connecting at once is refused. Print Serving only once the socket accepts; then drop the skill's retry advice.
