---
type: is
id: is-01m6f39zpnk9rc3kjy552b88qj
title: "Step 4: changed files in a row, expandable like a folder"
kind: feature
status: open
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies:
  - type: blocks
    target: is-01m2nz9gwd4wyxmrpx49cp9yck
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6f3a9djmnfvp42fmnwhwtr7
  - is-01m6f3a9tmf2t5m4pcb97gfr0j
  - is-01m6f3aa89emxbf0rwesa8gt7x
  - is-01m6f3aapq93hetda33rkdc9zv
  - is-01m6f3dkmagq7az0j52zq4je42
created_at: 2026-11-02T21:40:35.668Z
updated_at: 2026-11-02T22:39:08.235Z
---
Delivery step 4, added 2026-11-02. A row is a container: it expands to its changed files as a tree using the Files tree's row contract, from one gh request per 100 files with no Git. File rows open /pull/<n>/files/<path>. See the plan's Changed Files in a Row.

## Notes

2026-11-02: the performance study has reported (exp-040 on origin/claude/v012-pr-review-perf). The gate on the tree's shape and keyboard is lifted; jump-scrolling waits for the scrollToFile contract (mb-zx9q). Binding: build the tree from a file list and never from hydrated documents. The plan's gh pulls/<n>/files list satisfies this and needs no Git. A windowed list is likely needed past a few hundred files, and the tree must be bounded or virtualized at 1,183 rows.

2026-11-02: GATE. Do not fix this step's data shape before the large-pull-request performance study on branch claude/v012-pr-review-perf reports; the other session will message its result. It may recommend splitting the manifest from the patches, virtualizing, and a changed-files list, which overlaps this tree. MAX_HYDRATED_FILES and MAX_MANIFEST_FILES bear on it. Stress case: 1,183 files, +281,131 lines.
