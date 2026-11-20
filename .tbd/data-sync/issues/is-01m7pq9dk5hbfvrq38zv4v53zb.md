---
type: is
id: is-01m7pq9dk5hbfvrq38zv4v53zb
title: CHANGELOG.md conflicts on every merge to main serialize landing
kind: task
status: closed
priority: 2
version: 11
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/585
    at: 2026-11-20T17:01:15.434Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
parent_id: is-01m7wysgm9rg3fdch55nst1wrn
hold: null
hold_until: null
created_at: 2026-11-18T07:00:11.492Z
updated_at: 2026-11-20T19:13:12.261Z
started_at: 2026-11-18T22:09:13.346Z
closed_at: 2026-11-18T23:32:24.969Z
close_reason: "Merged in #585"
resolution: null
duplicate_of: null
extensions:
  linear:
    id: bba7e3df-b9d9-400b-a7eb-fbb09b374ac9
    linked_at: 2026-11-20T18:00:54.162Z
---
Overnight 2026-11-18 every merge to main made each open PR with an Unreleased entry conflict in CHANGELOG.md (both sides add at the top of Unreleased), forcing a merge-up and a fresh ~35-job CI run per PR per landing. Options: (a) .gitattributes 'CHANGELOG.md merge=union' (built-in driver; verify GitHub's mergeability check and merge honor it, and that union keeps entries separated by a blank line); (b) changelog fragments (one file per change under changelog.d/, assembled at release). Measure which GitHub honors before choosing.

## Notes

2026-11-18: tested option (a). With CHANGELOG.md merge=union in .gitattributes on both sides, local git merge-tree merged two top-of-Unreleased additions cleanly, but GitHub's server-side merge (POST /repos/{owner}/{repo}/merges between two scratch branches, since deleted) returned 409 Merge conflict: GitHub ignores merge=union. Option (a) is out. Remaining: (b) changelog fragments, one file per change (e.g. changelog.d/<bead>.md), assembled into CHANGELOG.md at release.

2026-11-18: implemented option (b) in PR #585 (branch claude/changelog-fragments): changelog.d/<bead>.md fragments; devtools/changelog.py check/show/assemble; make lint-check runs `check --against origin/main`, which fails a branch whose Unreleased section gains entries (edits and assembled fragments pass). Release checklist (docs/publishing.md) runs assemble in the release-prep PR. After merge every open PR that adds an Unreleased bullet must move it into changelog.d/<bead>.md.

2026-11-18: PR #585 merged 23:32Z (merge f9198f46d, head 7dabb3209). Follow-up commit 7ac78f6cd: entries already at the REF tip are known, so an uncommitted merge of main is not flagged. Full PR CI green at 2b286810b (run 44411188383); later PR runs and main push run 44421606268 were cancelled (lint and goldens 3.12 passed there); main run 44421892715 for 729b67553 was queued at report time. #583 already moved its entry to changelog.d/mb-hqje.md.
