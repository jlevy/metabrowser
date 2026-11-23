---
type: is
id: is-01m82szzfax1dcgyjtrbn87gcz
title: Probe tasks join the coordinator's job bound and are cancelled at shutdown
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-22T23:38:21.012Z
updated_at: 2026-11-22T23:38:21.012Z
---
From PR #709 K3 (https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6015081008). ServedPull probe tasks are tracked only by their ServedPull: they are outside the refresh coordinator's job bound, so a script asking many cached numbers within one probe's life (up to 30 s) runs that many gh processes at once, and nothing cancels a running probe when the server shuts down. Round 1 fixed the rest of K3 (any exception now marks the probe failed; _keep keeps a probing pull). Done: a bound on concurrent probes across numbers, and cancellation at shutdown, with tests.
