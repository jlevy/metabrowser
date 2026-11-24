---
type: is
id: is-01m85d3bsk35damt0fgwsq35h3
title: Bound a first clone by progress, not the acquisition deadline
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-23T23:50:43.763Z
updated_at: 2026-11-23T23:50:43.763Z
---
From review A finding A1 (Medium) of https://github.com/jlevy/metabrowser/pull/768 (https://github.com/jlevy/metabrowser/pull/768#pullrequestreview-6031209981).

PR 768 removed MAX_FIRST_CLONE_KB, the size limit that stood in for the acquisition deadline (GIT_ACQUISITION_TIMEOUT_S in src/metabrowser/git/process.py). A first clone is now refused only when it would not fit on the cache's volume, so a clone too large to finish inside the deadline starts, downloads for the whole deadline, and is stopped with nothing published; every rerun does the same. Example: 1,570,073 KB reported at the slowest measured first-clone rate (1,820 KB/s, pack 1.1 times the reported size) needs about 949 s.

A clone that is still making progress should not be killed at the wall-clock deadline. The low-speed bound in src/metabrowser/cache/origin.py (HTTP_LOW_SPEED_LIMIT_BYTES, HTTP_LOW_SPEED_TIME_S) already ends a stalled transfer once its connection is up. Decide what bounds a first clone instead: no wall-clock cap while progress continues, a cap that scales with the reported size, or a progress-based bound. Note what depends on the deadline today: RESERVATION_WAIT_S (cache/acquire.py), ELSEWHERE_WAIT_S (mirror_refresh.py), _REFRESH_DRAIN_S (cli/api_cli.py), the pull_refs deadline, and the reasoning at _NOT_RETRIED_UNASKED in src/metabrowser/checkout_store.py. The first-clone throughput measurements sit beside GIT_ACQUISITION_TIMEOUT_S in src/metabrowser/git/process.py.
