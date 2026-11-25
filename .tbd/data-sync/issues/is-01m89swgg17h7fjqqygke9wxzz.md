---
type: is
id: is-01m89swgg17h7fjqqygke9wxzz
title: "PR page stack button: show the author after the PR number"
kind: task
status: in_progress
priority: 1
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/843
    at: 2026-11-25T17:50:08.715Z
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T16:51:08.415Z
updated_at: 2026-11-25T19:14:36.167Z
started_at: 2026-11-25T16:52:51.739Z
---
User request: 'the stack button on the main PR page should also list the author after the PR number.' The button reads title, then '1/6 · #455 · author', in the same order as the Pulls row run (mb-rb3n). Keep the menu member rows consistent with it.

## Notes

Decisions (2026-11-25), recorded from the coordinator's relay of the user's words:
- First the user chose "menu rows only": the stack button keeps its Layers icon and "1/6", and only the stack menu's member rows get the author.
- The user then reversed that: "show authors wherever we show PR numbers and stacks unless there is, for some reason, not room for it." That reversal replaces "menu rows only" and is now the design-system rule "Authors Follow Pull Requests" (docs/design-system.md).
- Done in PR #843: Pulls rows; stack menu members (authors and avatars from the stacks route, beside its titles); a guide's pull request rows (guided_review.py `_pull_targets` carries author and avatar).
- The stack button stays exempt, for lack of room, and the rule says why. Measured in headless Chrome 152 on 2026-11-25 with the header check's fixtures: an author in the chip (a dot, a 16 px avatar, and a short login) is 58 px wide, 64 px with its gap. At a 360 px pane it left the row of ages 25 px of the 89 px they had, and a merged pull request's none. At 560 px it cut a closed pull request's ages from 284 px to 232 px. At 980 px it fit.
- The stack page's member rows are left to the stack-page rebuild. The remaining surfaces (Quick Search, the ref selector, a guide's file bar, the merged header) are mb-152g.
