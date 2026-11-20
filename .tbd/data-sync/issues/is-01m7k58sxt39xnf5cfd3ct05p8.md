---
type: is
id: is-01m7k58sxt39xnf5cfd3ct05p8
title: Each Pulls row has a third line, its brief change line ('21 A, 15 M, 7 D · +1,234 −567'), which carries the chevron for its changed files, collapsed by default
kind: feature
status: closed
priority: 1
version: 20
labels:
  - linear
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
child_order_hints:
  - is-01m7k58ts482vv1rh5fe1b96dr
  - is-01m7k58vaskn60ztckx9zeyyfz
  - is-01m7k58wccbmkccmwgm6rm7vk9
  - is-01m7ke42d71rkwxrpxkpnnz9d0
  - is-01m7ke9kd4ekcemwjbhgj1kwcp
  - is-01m7ke9kwj6q47jz1wf5j14mpf
  - is-01m7ke9mbv0r3w764d33ztww9e
  - is-01m7ke9mvh8a85vpdzvpres150
  - is-01m7ke9nakndr3207myrnt0ed3
  - is-01m7ke9nvd8389gt52ka8e83j5
  - is-01m7ke9pck9d1a248dcned2bz4
  - is-01m7ke9pw595h2hyw98s0bnbvm
  - is-01m7ke9qbrqvawjysdkrst6ahc
  - is-01m7ke9qvd4ny702gtyy15kzfb
  - is-01m7ke9rg45z8ngbqmdcc4dbbm
  - is-01m7ke9s0nfjbdz4jz7w3e1r6k
created_at: 2026-11-16T21:47:33.689Z
updated_at: 2026-11-20T17:00:14.849Z
closed_at: 2026-11-17T03:06:15.567Z
close_reason: "Merged in #491 (ae554dda8)"
resolution: null
duplicate_of: null
---
Owner, 2026-11-16: 'We should have the abbreviated summary for "21 A, 15 M, 7 D +1,234 −567" just as it is on a third line in the nav bar for each PR, and then make that the chevron collapsible part, with the file change summary below it, by default not expanded. In this way, we don't have the pull request expansion be as extensive initially, and we don't auto-open it unless the user clicks on the actual chevron. Then, when they do up and down arrows, it doesn't open the PR review items. It lets them see the size of each change. And by pressing Enter, they could open the expanded view there, but only on the summary line. this is an abbreviated summary line, so it doesn't mention the total number of file changes. It just lists the adds, removes, deletes, and line changes in exactly the same format, with a small bullet in between them. In the same coloring as on our other summaries'

## Notes

2026-11-17 handoff: PR #491 (claude/pulls-row-change-line, base main) review A addressed (A1-A12 fixed, A13 -> mb-jb7w), main merged, CI green at a4bc127ce; Review A disposition reply NOT yet posted. Post it, then merge; close mb-d0a3 mb-h0ml mb-1l4i and this. Plan row 30/Phase 30 added by this PR; after it merges move plan-2026-11-15 to specs/done (mb-p8et).
