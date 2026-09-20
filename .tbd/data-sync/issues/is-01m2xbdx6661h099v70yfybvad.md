---
type: is
id: is-01m2xbdx6661h099v70yfybvad
title: Upstream reviewable-unit PR rules to tbd shortcuts
kind: task
status: closed
priority: 2
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/tbd/pull/316
    at: 2026-09-19T18:28:40.065Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/219
    at: 2026-09-19T18:28:40.066Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-09-19T17:29:07.525Z
updated_at: 2026-09-20T05:50:26.424Z
started_at: 2026-09-19T17:31:01.867Z
closed_at: 2026-09-19T18:28:40.820Z
close_reason: "Upstream reviewable-unit rules in tbd#316; metabrowser agents load the forked shortcuts via #219 until get-tbd ships."
resolution: null
duplicate_of: null
---
tbd already has stacked-prs (opt-in, one concern per layer, prefer fewer larger layers) and implement-beads (one PR at end of a batch). Agents still open one PR per bead and chain them with informal --base. Add a reviewable-unit gate to create-or-update-pr-simple, strengthen stacked-prs Layer Discipline, and state beads≠PRs in plan-implementation-with-beads and implement-beads. Upstream tbd, not a metabrowser overlay. Do not land PRs as part of this bead.

## Notes

Closed. Policy lives in tbd #316 https://github.com/jlevy/tbd/pull/316 (CI green). Temporary metabrowser docs/tbd fork is #219 https://github.com/jlevy/metabrowser/pull/219 until get-tbd ships. Not in AGENTS.md. #219 lint fails on the anyio 4.14.1 audit (same advisory as dependabot #207 / HTML #209 lock bump). Unfork after tbd ships.
