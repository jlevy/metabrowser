---
type: is
id: is-01m79y5fzh3q0gcmhx66b0g1ts
title: "Branch chips: one font size and one color system everywhere"
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-13T07:50:15.280Z
updated_at: 2026-11-13T08:30:16.952Z
---
The user, 2026-11-12: the branch names inside the little ref chips are not the same font size in the PR view and in the Git commit view, and the system for their colors doesn't seem consistent. Make the font size consistent for branch names everywhere, and make the color system consistent (which kind each chip gets, and what each kind looks like), documented in docs/design-system.md. Builds on #385 (colors) and #390 (merge arrows); stacked on #390's branch.

## Notes

2026-11-13: jlevy/metabrowser#393 (claude/ui-ref-chip-system, stacked on #390): 415ab896 (commit summary and tooltip show refs; /api/git/refs has is_trunk) and 9808db91 (one .git-ref size, 12px everywhere; kind system documented in design-system 'Branch Chips'; HEAD ring visible). Comparison sheets checked by the coordinator; review A running. Open decision noted by the author: no trunk form on a PR's base chip.
