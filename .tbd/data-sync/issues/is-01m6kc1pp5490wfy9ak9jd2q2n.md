---
type: is
id: is-01m6kc1pp5490wfy9ak9jd2q2n
title: Correct QA lifecycle, linked-lender and measurement checks
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:30:19.200Z
updated_at: 2026-11-04T17:21:01.633Z
closed_at: 2026-11-04T17:21:01.633Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Documentation review D18: Phase7 still calls the implemented PR list deferred; an overlay pass universally demands seconds/kilobytes despite legitimate recorded larger/slower runs; the linked-worktree retry changes cwd but retains the original --checkout lender and assumes .git is a directory; an existing-empty-cache probe is not restored to the absent path expected later. Correct these four manual-playbook conditions against actual source and recorded evidence. Gate borrowing/no writes/diff correctness, record time/bytes without new thresholds, explicitly supply the linked worktree and resolve common Git storage. No product change.
