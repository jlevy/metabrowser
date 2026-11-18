---
type: is
id: is-01m7m7pqxe5kz3rq7pngtmfstm
title: 'Diff file links: one "View on branch" that opens the file in the normal UI; no standalone revision page'
kind: feature
status: closed
priority: 1
version: 2
labels:
  - ui
  - diff
  - pulls
dependencies: []
created_at: 2026-11-17T07:49:21.958Z
updated_at: 2026-11-17T19:07:46.364Z
closed_at: 2026-11-17T19:07:46.362Z
close_reason: Done in jlevy/metabrowser#511 (claude/view-on-branch); render bound split to mb-273l
resolution: null
duplicate_of: null
---
On a diff (a pull request's Changes, a commit's diff), each file bar has "View at base"/"View at parent" and "View file". On a pull request these open the GitHub plugin's revision page (snapshot_route, pull_snapshot.py), a standalone page with no navigation, tree, or context. Such pages should not exist. Replace both with one link, "View on branch", that opens the file in the normal UI as if navigated to at that branch (Files tab, its tree, the ref selector naming the branch). Review the whole design systematically; get an independent Fable review.
