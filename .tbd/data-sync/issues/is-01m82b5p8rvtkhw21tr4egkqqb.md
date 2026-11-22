---
type: is
id: is-01m82b5p8rvtkhw21tr4egkqqb
title: Replace branch and tag hover-copy controls with action menus
kind: feature
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/692
    at: 2026-11-22T19:44:21.292Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T19:19:19.574Z
updated_at: 2026-11-22T20:06:14.005Z
started_at: 2026-11-22T19:38:04.416Z
closed_at: 2026-11-22T20:06:13.982Z
close_reason: "Merged reviewed #692 at 0e4e627e6470 after exact head fd9deb983 passed general and native CI. Chrome checked the actual tag route, fork destination, keyboard and fixed-width trigger."
resolution: null
duplicate_of: null
---
Cover commit history and detail, selected ref, and PR head/base. The chip opens a menu with type and exact name, copy-name, Metabrowser browsing, and a GitHub destination where known. Reveal the down chevron as an overlay on hover, focus, and open; reserve no chip width. Remove the old copy-only affordance.
