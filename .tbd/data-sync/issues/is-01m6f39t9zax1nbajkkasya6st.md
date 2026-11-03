---
type: is
id: is-01m6f39t9zax1nbajkkasya6st
title: "Spec: GitHub Pulls tab for mirrors and local checkouts"
kind: epic
status: in_progress
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
child_order_hints:
  - is-01m2h7hrjfx06hzpr7ptz7k9wn
  - is-01m6f39wqb7nqd20w7z5vpw9vh
  - is-01m2h7jjgpzyfbf10238j32z6q
  - is-01m6f39zpnk9rc3kjy552b88qj
  - is-01m2nz9gwd4wyxmrpx49cp9yck
  - is-01m6f3a2f5v5bkym87p85a0wq2
  - is-01m6fk7mz18kwadmnr0w05da09
  - is-01m6fvyjc2bffw1nzzywz9z1y6
created_at: 2026-11-02T21:40:30.142Z
updated_at: 2026-11-03T06:47:08.978Z
---
Every pull request of a GitHub repository in a Pulls tab beside Files and Git, newest first, with GitHub-style state icons. Each row expands in place to its changed files as a tree, like a folder. The pane shows this tab at a pull request's address. Works on a mirror and on an existing checkout, with nothing written to the user's repository. Delivered as a native stack above the v0.12 stack. See the plan's Delivery.

## Notes

2026-11-03 status: the stack is native stack 286 (#279 → #281 → #285), based on claude/v012-overlay-acquisition, the top of stack 278. Step 1 (#279, head 1cb84734) and step 2 (#281, head 5d5546fc) are implemented, reviewed, addressed and green, and wait for the owner's merge decision. Step 3 (#285, head 766a4c3b) is green, with its round-2 review findings being addressed (mb-7d12). Step 4 (claude/pulls-4-files): data half done, second half in progress. Step 5 (claude/pulls-5-checkout): in progress. Step 6: plan revised to the overlay of the served checkout, not started. Strong-tier pass owed on reviews run on Opus: mb-wlxn.
