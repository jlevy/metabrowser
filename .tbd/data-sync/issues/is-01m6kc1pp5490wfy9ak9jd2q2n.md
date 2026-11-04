---
type: is
id: is-01m6kc1pp5490wfy9ak9jd2q2n
title: Correct QA lifecycle, linked-lender and measurement checks
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:30:19.200Z
updated_at: 2026-11-04T13:30:19.200Z
---
Documentation review D18: Phase7 still calls the implemented PR list deferred; an overlay pass universally demands seconds/kilobytes despite legitimate recorded larger/slower runs; the linked-worktree retry changes cwd but retains the original --checkout lender and assumes .git is a directory; an existing-empty-cache probe is not restored to the absent path expected later. Correct these four manual-playbook conditions against actual source and recorded evidence. Gate borrowing/no writes/diff correctness, record time/bytes without new thresholds, explicitly supply the linked worktree and resolve common Git storage. No product change.
