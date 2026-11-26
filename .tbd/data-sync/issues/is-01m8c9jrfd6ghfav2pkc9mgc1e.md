---
type: is
id: is-01m8c9jrfd6ghfav2pkc9mgc1e
title: Let a one-shot metab --api drain jobs started while it drains
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
labels: []
dependencies: []
parent_id: is-01m8bmw4sdejvn3fx7tjgeyvpz
created_at: 2026-11-26T16:03:54.989Z
updated_at: 2026-11-26T16:03:54.989Z
---
RefreshCoordinator.drain waits only for jobs running when it is called. In the merge readiness stack, pulls-refresh starts a separate base-look job (pull_status_scan.look_key) that may start the status scan; under a one-shot metab --api, a scan started during the drain is cancelled at aclose. A long-running server is unaffected. Drain until no job remains (bounded), or have the look job await the scan it starts. Found while fixing the layer 4 review.
