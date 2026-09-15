---
type: is
id: is-01m2h99j30ekrbn0zjvc6h711m
title: "PR #125 review A-R4 C-R10 D-R3: own bounded provider snapshot reclamation"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:00:54.750Z
updated_at: 2026-09-15T01:38:05.693Z
closed_at: 2026-09-15T01:38:05.692Z
close_reason: "Fixed A-R4/C-R10/D-R3: bounded provider snapshot retention by current, last-complete, one diagnostic predecessor, explicit pins, reachability, and reader leases; assigned the implementation and race/recovery tests to mb-i3xc."
resolution: null
duplicate_of: null
---
Deduplicated PR #125 architecture A-R4, contracts C-R10, and delivery D-R3. Assign measured generation bounds, manifest reachability sweeping, live-reader leases, crash and orphan recovery, and last validated reachable set protection to a blocking provider-store delivery bead and focused tests.
