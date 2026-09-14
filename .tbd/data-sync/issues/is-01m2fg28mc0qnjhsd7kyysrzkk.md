---
type: is
id: is-01m2fg28mc0qnjhsd7kyysrzkk
title: "PR #119 review S1: sibling rollup ETag/304 tests exposed to watcher version moves"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m2fg26ysev7mq8czs73qyrvf
created_at: 2026-09-14T08:20:46.860Z
updated_at: 2026-09-14T08:53:38.701Z
closed_at: 2026-09-14T08:53:38.699Z
close_reason: "Fixed in PR #119 at 5aeeac26: revalidate and payload/304 rollup tests run with watch_mode=off and assert the version held; late-write injection fails the old versions 10/10, new pass 10/10. https://github.com/jlevy/metabrowser/pull/119#issuecomment-5661449001"
resolution: null
duplicate_of: null
---
tests/test_rollup_route.py test_rollup_revalidates_and_reuses_unchanged_body and test_rollup_payload_and_etag_share_one_version compare ETags across requests with the watcher live. Apply watch_mode=off plus a version-held assertion. PR #119.
