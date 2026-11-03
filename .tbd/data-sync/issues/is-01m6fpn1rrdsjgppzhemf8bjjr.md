---
type: is
id: is-01m6fpn1rrdsjgppzhemf8bjjr
title: "PR #281 D2: request_commit_fetch drops a refused attended job, so a commit page says the origin lacks a commit whose fetch never ran"
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6fpn0yb9yn4kakx1qp787e4
created_at: 2026-11-03T03:18:41.175Z
updated_at: 2026-11-03T03:18:41.175Z
---
Low. src/metabrowser/mirror_refresh.py:841-845, src/metabrowser/static/source-freshness.js:583-614. Fix: carry the companion's answer in the /api/source/refresh envelope as pull_refresh and let describeMissingCommit say when it is too_many. Review: https://github.com/jlevy/metabrowser/pull/281#pullrequestreview-5746822976 (PR #281, head 7bef1356).
