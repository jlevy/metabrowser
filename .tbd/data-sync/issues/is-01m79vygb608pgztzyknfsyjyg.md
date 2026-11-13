---
type: is
id: is-01m79vygb608pgztzyknfsyjyg
title: Show every merge as source → target, left to right, in one notation
kind: feature
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-13T07:11:29.125Z
updated_at: 2026-11-13T07:11:29.125Z
---
The user, 2026-11-12: wherever a PR merges one branch into another, show the source branch to the left of the target with an arrow between them, left to right (some-branch → main), never 'from ... into ...' and never target ← source. This applies on the Pulls list (the navigation page; today 'main ← claude/x') and the PR page (today 'wants to merge 1 commit into topic from wip'). Make it one consistent design-system notation for merges everywhere it appears, and document it in docs/design-system.md. Stacked on #385's branch (claude/ui-branch-colors-badges); does not change the merge sequence.
