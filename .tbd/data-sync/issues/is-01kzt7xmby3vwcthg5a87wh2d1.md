---
type: is
id: is-01kzt7xmby3vwcthg5a87wh2d1
title: "PR #32 review MB32-R1: make check-api timeouts actionable"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzt7x3qqb7y2qgpbxhjg3k3x
created_at: 2026-08-12T05:42:59.709Z
updated_at: 2026-08-12T05:56:10.644Z
closed_at: 2026-08-12T05:56:10.643Z
close_reason: "Fixed in c263112: the transcript reports explicit index outcomes and --index-timeout configures the wait; focused and golden tests cover the behavior."
---
PR #32 senior review MB32-R1 (Medium). src/metabrowser/cli/check_api.py: _wait_for_index and run_api_check. Emit an explicit index outcome in the transcript for done, failed, or timeout; validate whether a configurable timeout belongs in this PR.
