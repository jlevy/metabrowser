---
type: is
id: is-01m7hdmhxzvcwtxzyckhk5zsty
title: "PR #463 A2: Diff summary header's chevron, ring and hover ground are off its rows' geometry"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjqx287ha000smyytqswb
hold: null
hold_until: null
created_at: 2026-11-16T05:35:18.462Z
updated_at: 2026-11-16T05:47:56.884Z
started_at: 2026-11-16T05:47:56.373Z
closed_at: 2026-11-16T05:47:56.883Z
close_reason: "Declined on #463: superseded by #472, which redefines the header as the tree's root with rows one --tree-indent in (--diff-summary-toggle-pull, --diff-summary-header-inset). Doc claim narrowed in 6c0bd6f1f. The header's ring and hover ground are unchanged and unmeasured at #472; the top layer's review measures them."
resolution: canceled
duplicate_of: null
---
src/metabrowser/builtin_plugins/diff/styles.css:58-80, docs/design-system.md:1300: header chevron 4px left of a first-level folder's; ring on the chevron slot's first 2px; ground starts at 8px. 'The header hovers and rings as its rows do' overclaims. Severity: Low. PR #463, Review A round 1: https://github.com/jlevy/metabrowser/pull/463#pullrequestreview-5915439143
