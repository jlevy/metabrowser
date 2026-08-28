---
type: is
id: is-01m134g82eez4ccvrza9w9k699
title: "D11: ref resolution unspecified against a clone's real namespace"
kind: chore
status: closed
priority: 3
version: 2
spec_path: docs/project/reviews/review-2026-08-27-independent-design-review.md
labels: []
dependencies: []
parent_id: is-01m134g1jm1dr1xgfhct0ja3c7
created_at: 2026-08-28T02:52:07.116Z
updated_at: 2026-08-28T03:02:52.440Z
closed_at: 2026-08-28T03:02:52.439Z
close_reason: Fixed in dbd5521 (D11). See the commit message and the plan diff.
resolution: null
duplicate_of: null
---
Post-clone ref resolution must say what it resolves against: non-default branches exist only under refs/remotes/origin/ in a fresh clone, so resolving a bare branch name against local refs/heads/ finds only the default branch. Also unhandled: the raw.githubusercontent.com/<owner>/<repo>/refs/heads/<branch>/<path> form. Neither is in the goldens.
