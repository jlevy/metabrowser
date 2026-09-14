---
type: is
id: is-01m2fcza6ee3hqv561y7wz6av2
title: "PR #118 review R3: box-stays-centered assertions cannot fail"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2fcz83jz15cmfj6yfdvm1sq
created_at: 2026-09-14T07:26:44.427Z
updated_at: 2026-09-14T07:58:40.130Z
closed_at: 2026-09-14T07:58:40.129Z
close_reason: "Fixed in 0f399e54 (https://github.com/jlevy/metabrowser/pull/118): test scans every baseline rule in core and plugin stylesheets against per-state row fixtures with a selector matcher; 16 mutations caught."
resolution: null
duplicate_of: null
---
PR #118 review R3 (Low). tests/test_design_vocabulary.py:82-85 only reads the first exact-selector rule for .tree-item-icon, .tree-folder > .tree-toggle, .git-graph-refs. Scan every rule targeting the boxes or wildcard children of the rows instead.
