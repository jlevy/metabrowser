---
type: is
id: is-01m7pvqa59443hvcrrczxef78t
title: "Dry run of present mode: report whether the repository is cached, with a light cache check"
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7nyeb57h28trbdp2m1hy2wk
created_at: 2026-11-18T08:17:41.032Z
updated_at: 2026-11-18T16:22:54.933Z
---
Optional from PR #539: the app cache lookup (paging /api/cache/sources) costs about 0.8 s with 12 cached sources; adding cache.acquire to the dry run costs about 250 ms of imports per link, so it needs a lighter check.

## Notes

2026-11-18, review C13 on PR #539: nothing is on screen while the app asks the cache before a new repository session (the dry run, then one metab per page of /api/cache/sources: about 0.6-0.8 s a page, measured by review C). This bead is the fix, and it must cover a cache of more than one page (RepositoryCache.pageLimit = MAX_PAGE_LIMIT sources a page, up to RepositoryCache.maximumPages), where the wait is that cost times the pages read; a cache state in the dry run answers in one call however many sources there are. Since review C's round, the lookup runs in the link's turn and the question waits beside the queue (CloneQuestions), so other links are held only for the lookup, not for the question.
