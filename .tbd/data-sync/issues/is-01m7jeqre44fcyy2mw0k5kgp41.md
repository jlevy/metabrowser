---
type: is
id: is-01m7jeqre44fcyy2mw0k5kgp41
title: "PR #452 A11: the user guide does not say which directories are not watched live"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpct6qpjeqfpyetf79fef
hold: null
hold_until: null
created_at: 2026-11-16T15:13:46.435Z
updated_at: 2026-11-16T15:27:49.390Z
started_at: 2026-11-16T15:14:17.400Z
closed_at: 2026-11-16T15:27:49.389Z
close_reason: "Fixed in 3ef505070: When a Live Update Is Missing step 2 names the skipped tool directories; pinned by test_user_guide_values (DefaultFilter.ignore_dirs and run_watcher passing no watch_filter). Behavior change remains mb-xr2g."
resolution: null
duplicate_of: null
---
Suggestion. watch_backends.py:27-30; docs/browsing-files.md:200-213. Review A on PR #452: https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5922214786
