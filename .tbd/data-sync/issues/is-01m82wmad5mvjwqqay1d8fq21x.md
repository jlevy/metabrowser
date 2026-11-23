---
type: is
id: is-01m82wmad5mvjwqqay1d8fq21x
title: Close the branch dropdown when its chip is clicked again
kind: bug
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/716
    at: 2026-11-23T00:42:48.407Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:24:24.685Z
updated_at: 2026-11-23T00:59:20.642Z
started_at: 2026-11-23T00:25:32.529Z
closed_at: 2026-11-23T00:59:20.642Z
close_reason: "Independently reviewed and merged in #716 at ca2beb4cb. Real Chrome and exact hosted tests passed for nested folder menus, commit copy, shared caret motion and repeat-click dismissal."
resolution: null
duplicate_of: null
---
A second click on the same branch or tag chip closes its menu across inline and sibling-overlay placements. Preserve focus, opening another chip, outside dismissal, and nested folder menu behavior.
