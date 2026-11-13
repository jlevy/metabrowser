---
type: is
id: is-01m79vygb608pgztzyknfsyjyg
title: Show every merge as source → target, left to right, in one notation
kind: feature
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T07:11:29.125Z
updated_at: 2026-11-13T08:48:07.262Z
closed_at: 2026-11-13T08:48:07.261Z
close_reason: "Done in jlevy/metabrowser#390: mb.mergeRefs, source → target on the Pulls row and PR header, documented in design-system 'Merge Direction'. Reviews A, B, C (approve with a Low, fixed in ff93f82a). Merging once CI is green."
resolution: null
duplicate_of: null
---
The user, 2026-11-12: wherever a PR merges one branch into another, show the source branch to the left of the target with an arrow between them, left to right (some-branch → main), never 'from ... into ...' and never target ← source. This applies on the Pulls list (the navigation page; today 'main ← claude/x') and the PR page (today 'wants to merge 1 commit into topic from wip'). Make it one consistent design-system notation for merges everywhere it appears, and document it in docs/design-system.md. Stacked on #385's branch (claude/ui-branch-colors-badges); does not change the merge sequence.

## Notes

2026-11-12: jlevy/metabrowser#390 (claude/ui-merge-arrows, base main): mb.mergeRefs helper, the Pulls row and PR header read source → target, design-system section 'Merge Direction', focused test. Also fixes the Pulls row's arrow vanishing under text-overflow: ellipsis. Screenshots checked by the coordinator; review A running.
