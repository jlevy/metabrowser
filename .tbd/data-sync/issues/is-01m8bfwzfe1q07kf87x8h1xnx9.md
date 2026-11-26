---
type: is
id: is-01m8bfwzfe1q07kf87x8h1xnx9
title: "macOS spike: the three plugins in a worker under a confinement profile"
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8bfx1aaxf7qyzn1n2h1ap4v
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-26T08:35:06.862Z
updated_at: 2026-11-26T09:20:28.198Z
started_at: 2026-11-26T09:20:28.198Z
---
Phase 0 spike, macOS (plan: Key Decision 11, How It Fits the macOS App). Decides Key Decision 11 for macOS before Phase 4. Run the three downstream plugins in the plan's worker under a sandbox-exec profile rendered from a Confinement: read the plugin environment, its base interpreter, the clone, and the served folder; write a scratch folder; no network; process-fork and exec of tools inside the grants. Learn which further grants a real Python environment needs (mach-lookup names, sysctl, /private/var/db, temporary folders, native extension loading), whether the result can still be stated in one consent sentence, and what the prefix costs per worker start. Also check the inferred claims: that a confined child cannot use the app's privacy grants outside its roots, that the app's hardened runtime does not stop sandbox-exec children, that a metab started inside another sandbox finds no backend, and that the app's group stop plus the lifeline leave no worker. Deliver a results file beside the spike and an update to the plan's enforcement matrix, whose macOS column is today the PDF child's profile and is not run for a worker.
