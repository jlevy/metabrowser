---
type: is
id: is-01m89vjxvyyjj0qpg03ewb06y4
title: "Skill: guided-review pins from Metabrowser, deferred files' hunks, step-less outline, stack guide gaps"
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m8806zrnxn9jwj89hffd2yv7
hold: null
hold_until: null
created_at: 2026-11-25T17:20:51.580Z
updated_at: 2026-11-25T18:15:55.627Z
started_at: 2026-11-25T17:20:56.354Z
closed_at: 2026-11-25T18:15:55.624Z
close_reason: "Merged in #841"
resolution: null
duplicate_of: null
---
A fresh agent tested the installed metabrowser skill (main 4e5893d33) against metab 0.14.0.dev675 and found gaps in Write a Guided Review and Write a Stack Guide: (1) the PR merge_base recipe uses git merge-base origin/<base> <head>, which answers the head itself for a merged pull request, where the record's comparison.base is the pin the route checks; (2) a comparison hydrates only its first files and marks the rest deferred with no patch, and the skill does not say that &file=<path> on the comparison route answers one file with its hunks; (3) no route checks an unpublished block, and the skill does not give the interim: check ranges, publish, then read every step and fix; (4) the step-less guided-review call answers titles, outline, step_count and step 1, which the skill does not use; (5) group=type:docs holds changelog fragments, goldens, and fixtures; (6) a stack whose layers all merged, and reading a layer's description from the cached record; (7) stderr may carry slow server request lines. Fix each in skills/metabrowser/SKILL.md, verified against metab output, with golden pins for new recipes.

## Notes

PR https://github.com/jlevy/metabrowser/pull/841 (standalone, base main). Its guided review was pinned, checked, and confirmed with the fixed recipes: all 6 steps and every reference ready through the guided-review route. Not merged; the coordinator merges.
