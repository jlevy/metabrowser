---
type: is
id: is-01m6g1zdadpx3wxbsnzd6pesyh
title: "PR #284 E3: a cold comparison grows with the pull request, 0.46 s at 1,031 files and 0.95 s at 1,627"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6g1yw7yj073zja4jqvz0g8b
created_at: 2026-11-03T06:36:35.020Z
updated_at: 2026-11-03T06:36:35.020Z
---
Medium. sidekick.py:384 computes the manifest on the first request (git.py:402-420, one --raw --numstat -M50 -C run). Review: https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5747841588
