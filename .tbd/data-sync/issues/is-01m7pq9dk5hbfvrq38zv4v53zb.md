---
type: is
id: is-01m7pq9dk5hbfvrq38zv4v53zb
title: CHANGELOG.md conflicts on every merge to main serialize landing
kind: task
status: in_progress
priority: 2
version: 5
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-18T07:00:11.492Z
updated_at: 2026-11-18T22:24:11.480Z
started_at: 2026-11-18T22:09:13.346Z
---
Overnight 2026-11-18 every merge to main made each open PR with an Unreleased entry conflict in CHANGELOG.md (both sides add at the top of Unreleased), forcing a merge-up and a fresh ~35-job CI run per PR per landing. Options: (a) .gitattributes 'CHANGELOG.md merge=union' (built-in driver; verify GitHub's mergeability check and merge honor it, and that union keeps entries separated by a blank line); (b) changelog fragments (one file per change under changelog.d/, assembled at release). Measure which GitHub honors before choosing.

## Notes

2026-11-18: tested option (a). With CHANGELOG.md merge=union in .gitattributes on both sides, local git merge-tree merged two top-of-Unreleased additions cleanly, but GitHub's server-side merge (POST /repos/{owner}/{repo}/merges between two scratch branches, since deleted) returned 409 Merge conflict: GitHub ignores merge=union. Option (a) is out. Remaining: (b) changelog fragments, one file per change (e.g. changelog.d/<bead>.md), assembled into CHANGELOG.md at release.

2026-11-18: implemented option (b) in PR #585 (branch claude/changelog-fragments): changelog.d/<bead>.md fragments; devtools/changelog.py check/show/assemble; make lint-check runs `check --against origin/main`, which fails a branch whose Unreleased section gains entries (edits and assembled fragments pass). Release checklist (docs/publishing.md) runs assemble in the release-prep PR. After merge every open PR that adds an Unreleased bullet must move it into changelog.d/<bead>.md.
