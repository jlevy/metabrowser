---
type: is
id: is-01m1z5jw4bmyy5wd1enkrbvzzj
title: Repair shared tracker worktree bare setting during stack review
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-08T00:09:45.856Z
updated_at: 2026-09-08T00:10:09.710Z
closed_at: 2026-09-08T00:10:09.700Z
close_reason: Repaired only core.bare in the shared tracker worktree config. Synchronization then published the review records at 91221f97; repository and tracker sync status verified.
resolution: null
duplicate_of: null
---
Tracker sync worktree inherited core.bare=true from common Git configuration while the main checkout had its own false override. tbd sync reported Already in sync even though records were modified. Set core.bare=false only in the tracker worktree config, then tbd sync --issues published 14 new and 13 updated records at tracking commit 91221f97. Product code and global Git settings were unchanged.
