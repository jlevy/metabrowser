---
type: is
id: is-01m7paacr9fpsy85e4ktcv30nh
title: metab serve prints Serving before the socket accepts connections
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T03:13:31.909Z
updated_at: 2026-11-18T03:13:31.909Z
---
Deferred from PR #541 review A19 (predates that PR): the Serving line can appear before the listening socket accepts, so an agent connecting at once is refused. Print Serving only once the socket accepts; then drop the skill's retry advice.
