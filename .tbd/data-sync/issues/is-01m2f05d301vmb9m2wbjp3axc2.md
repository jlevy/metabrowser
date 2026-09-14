---
type: is
id: is-01m2f05d301vmb9m2wbjp3axc2
title: "PR #112 review R2: synchronize() after dispose() re-activates the tree scope"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2f05257wwkdtjwanq4bd016
created_at: 2026-09-14T03:42:52.511Z
updated_at: 2026-09-14T03:45:32.003Z
closed_at: 2026-09-14T03:45:32.002Z
close_reason: "Fixed in f67c6769: activateTreeScope now guards on !disposed; new check that synchronize after dispose publishes no scope event fails without the guard."
resolution: null
duplicate_of: null
---
PR #112, Low. activateTreeScope at src/metabrowser/static/tree-keyboard-navigation.js:173-177 has no disposed guard; the new call in repairAnchor (:338-342) re-activates the tree scope after dispose() (:652-666) and nothing deactivates it. Fix: guard with !disposed && !deactivateScope, plus a test that fails without the guard.
