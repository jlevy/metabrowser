---
type: is
id: is-01m7pvqa59443hvcrrczxef78t
title: "Dry run of present mode: report whether the repository is cached, with a light cache check"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7nyeb57h28trbdp2m1hy2wk
created_at: 2026-11-18T08:17:41.032Z
updated_at: 2026-11-18T08:17:41.032Z
---
Optional from PR #539: the app cache lookup (paging /api/cache/sources) costs about 0.8 s with 12 cached sources; adding cache.acquire to the dry run costs about 250 ms of imports per link, so it needs a lighter check.
