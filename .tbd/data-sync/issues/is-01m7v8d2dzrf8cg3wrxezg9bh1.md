---
type: is
id: is-01m7v8d2dzrf8cg3wrxezg9bh1
title: "Decide: under branch-follow, do a pull request's served head and its Changes diff follow new pushes?"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m7v8bs62dz0nqmqb9rnhgsdb
created_at: 2026-11-20T01:16:14.654Z
updated_at: 2026-11-22T21:24:40.234Z
closed_at: 2026-11-22T21:24:40.225Z
close_reason: "Decided by the owner 2026-11-22 (\"Take both\" in chat, accepting the recommendation): a pull request's served head follows new pushes like a branch, and Changes follows too, with a one-line note naming the old and new head and a way back to the old diff. Implementation: mb-6a6w."
resolution: null
duplicate_of: null
---
Today, on a repository URL, the served code stays on the head a pull request had until **Switch to the head**, and Changes keeps its diff with "New commits were pushed; updating." and **Show the newer changes** (docs/reviewing-pull-requests.md; pull-page.js).

refs/pull/<n>/head is a ref, so under the owner's 2026-11-19 rule ("we generally want the UI to follow the state of the repo") the served code would follow it like a branch. The Changes diff is the open question: following keeps the review current, but a reader partway through a diff would see it change under them.

Recommendation: the served code follows the head, as the mirror-follow bead does for branches. Changes follows too, with a one-line note naming the old and new head and a way back to the old diff.

## Notes

2026-11-22: more pressing now. The cadence work (epic mb-dip2, OS-627; mb-sjgl) has a visible pull request page probe GitHub every 5 s and refresh at once on a change. So a push during a review now brings **Switch to the head** and Changes' **Show the newer changes** within seconds, where before it took up to 90 s. The recommendation stands: the served code follows the head, and Changes follows with a one-line note naming the old and new head and a way back to the old diff. Waiting on the owner.
