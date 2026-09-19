---
type: is
id: is-01m2xbdx6661h099v70yfybvad
title: Upstream reviewable-unit PR rules to tbd shortcuts
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-09-19T17:29:07.525Z
updated_at: 2026-09-19T17:29:07.525Z
---
tbd already has stacked-prs (opt-in, one concern per layer, prefer fewer larger layers) and implement-beads (one PR at end of a batch). Agents still open one PR per bead and chain them with informal --base. Add a reviewable-unit gate to create-or-update-pr-simple, strengthen stacked-prs Layer Discipline, and state beads≠PRs in plan-implementation-with-beads and implement-beads. Upstream tbd, not a metabrowser overlay. Do not land PRs as part of this bead.
