---
type: is
id: is-01m6f39t9zax1nbajkkasya6st
title: "Spec: GitHub Pulls tab for mirrors and local checkouts"
kind: epic
status: in_progress
priority: 1
version: 18
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
  - is-01m6hkbt0t0qhvrhxhktgefe38
  - is-01m6hknzgxphza4kbk01qdxjka
  - is-01m6hp3w66pyvqttk9w3hbmj70
created_at: 2026-11-02T21:40:30.142Z
updated_at: 2026-11-03T21:47:47.269Z
---
Every pull request of a GitHub repository in a Pulls tab beside Files and Git, newest first, with GitHub-style state icons. Each row expands in place to its changed files as a tree, like a folder. The pane shows this tab at a pull request's address. Works on a mirror and on an existing checkout, with nothing written to the user's repository. Delivered as a native stack above the v0.12 stack. See the plan's Delivery.

## Notes

2026-11-03 FINAL READINESS at ea771741211193a387c1771e04df29b5a9698100. The full 14-PR stack is independently reviewed and ready for the owner's merge decision. All actual bases contain their lower layer, both native stacks match, every PR is open/non-draft and mergeable/clean, and all 171 CI jobs across 19 current-head workflow runs passed. Final make verify: 4712 Python passed, 9 expected skips, 373 transcript checks; dependency audits, distribution and isolated installed-wheel checks passed. Exact-head public live: 8 passed; fresh installed-wheel Chrome: 22 actions with 25 unchanged checkout/common-Git fingerprints. Managed repository URLs and existing main/linked checkouts pass. Final Review G: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . All findings have published dispositions; fixed threads are resolved, while rebutted/declined threads remain reviewer-visible. Completed stabilization/review beads are closed and residual baseline observer mb-czrw is under mb-2iok. Both WIP branches and the original local server remain unchanged. Frontend/backend ship together on one local server with explicit-number requests; compatibility-only work remains canceled. Historical timing evidence keeps its original source pins; no quiet-machine or universal 500ms claim. Quiet timings, remaining performance/browser/release follow-ups and explicit owner-merge beads remain open. No PR merged or history rewritten. After the owner merges stack278, unstack286, retarget279 to main and relink279/281/285/287/288 as documented on279.

Earlier chronological notes (superseded where they describe pending final gates):

2026-11-03 PAUSE POINT, final heads, all CI 9 of 9 green, every layer containing its base (claude/v012-overlay-acquisition at b29dc787): #279 9379cefe, #281 9fcb0c21, #285 d9bd5f56, #287 (draft) 2bf3d194, #288 (draft) fb780169. WIP branches, not in any PR, each needing its PR branch merged in before work resumes: wip/pulls-4-files fff7d6a3, wip/pulls-5-checkout 24a95778. Each PR's 'Status, 2026-11-03 (paused for a handoff)' section says what is next.

2026-11-03 HANDOFF (paused for another agent): stack 286 is #279 → #281 → #285 → #287 (draft) → #288 (draft), base claude/v012-overlay-acquisition (top of stack 278). Every layer contains its base; nothing was rewritten. Each PR's 'Status, 2026-11-03' section is the per-layer handoff. #279 and #281: done, awaiting the owner's merge. #285: two Qodo Lows open (mb-kstl, mb-qjpa) and a light follow-up review of 2cfed240 owed. #287: data half on its branch; second half on wip/pulls-4-files (fff7d6a3), never rendered in a browser. #288: plan revision on its branch; implementation on wip/pulls-5-checkout (24a95778). Step 6 not started. When stack 278 merges, stack 286's base must move to main: gh refuses a base edit inside a stack, so unstack 286, retarget #279, and relink with gh stack link --base main (it gets a new stack number). Strong-tier pass owed on Opus-run reviews: mb-wlxn. Leftover worktrees: metabrowser-pulls, -2, -3, -4 (on wip/pulls-4-files), -5 (on wip/pulls-5-checkout).

2026-11-03 status: the stack is native stack 286 (#279 → #281 → #285), based on claude/v012-overlay-acquisition, the top of stack 278. Step 1 (#279, head 1cb84734) and step 2 (#281, head 5d5546fc) are implemented, reviewed, addressed and green, and wait for the owner's merge decision. Step 3 (#285, head 766a4c3b) is green, with its round-2 review findings being addressed (mb-7d12). Step 4 (claude/pulls-4-files): data half done, second half in progress. Step 5 (claude/pulls-5-checkout): in progress. Step 6: plan revised to the overlay of the served checkout, not started. Strong-tier pass owed on reviews run on Opus: mb-wlxn.

2026-11-03 closure-scope clarification: retain this parent open while its explicit owner-merge conditions remain. mb-lnkl says its children stay in progress until the owner merges; mb-4nju says its children close at merge. Those rules apply to their own descendant chains, not automatically to siblings. mb-cbak and mb-r50o are direct children here; mb-zx9q is under mb-q3jt; mb-5bqy is under mb-r50o. None is a descendant of mb-lnkl or mb-4nju, and no equivalent merge-only rule was found in their parent chains. Their completed implementation/review work can be closed by the coordinator after final readiness gates without claiming that the stack has merged. mb-wlxn now has completed strong-review evidence; the old owed-review and unfinished-WIP notes are historical. No status, dependency, source, stack or remote state is changed by this clarification.
