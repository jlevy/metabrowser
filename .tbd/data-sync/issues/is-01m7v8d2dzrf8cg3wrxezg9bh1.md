---
type: is
id: is-01m7v8d2dzrf8cg3wrxezg9bh1
title: "Decide: under branch-follow, do a pull request's served head and its Changes diff follow new pushes?"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7v8bs62dz0nqmqb9rnhgsdb
created_at: 2026-11-20T01:16:14.654Z
updated_at: 2026-11-20T01:16:14.654Z
---
Today, on a repository URL, the served code stays on the head a pull request had until **Switch to the head**, and Changes keeps its diff with "New commits were pushed; updating." and **Show the newer changes** (docs/reviewing-pull-requests.md; pull-page.js).

refs/pull/<n>/head is a ref, so under the owner's 2026-11-19 rule ("we generally want the UI to follow the state of the repo") the served code would follow it like a branch. The Changes diff is the open question: following keeps the review current, but a reader partway through a diff would see it change under them.

Recommendation: the served code follows the head, as the mirror-follow bead does for branches. Changes follows too, with a one-line note naming the old and new head and a way back to the old diff.
