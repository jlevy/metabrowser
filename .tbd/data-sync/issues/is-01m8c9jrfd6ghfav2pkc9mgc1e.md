---
type: is
id: is-01m8c9jrfd6ghfav2pkc9mgc1e
title: Let a one-shot metab --api drain jobs started while it drains
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/909
    at: 2026-11-26T23:58:09.894Z
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8bmw4sdejvn3fx7tjgeyvpz
hold: null
hold_until: null
created_at: 2026-11-26T16:03:54.989Z
updated_at: 2026-11-27T00:04:01.758Z
started_at: 2026-11-26T22:24:38.389Z
closed_at: 2026-11-27T00:04:01.758Z
close_reason: Merged to main as jlevy/metabrowser#909.
resolution: null
duplicate_of: null
---
RefreshCoordinator.drain waits only for jobs running when it is called. In the merge readiness stack, pulls-refresh starts a separate base-look job (pull_status_scan.look_key) that may start the status scan; under a one-shot metab --api, a scan started during the drain is cancelled at aclose. A long-running server is unaffected. Drain until no job remains (bounded), or have the look job await the scan it starts. Found while fixing the layer 4 review.
