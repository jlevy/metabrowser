---
type: is
id: is-01m883wxdx6ysz42ekzs7p0h7d
title: "PR #801 A7: new copy says ref where the PR says branch or tag elsewhere"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m883v3q9d1nc4xypdrb2gbg1
hold: null
hold_until: null
created_at: 2026-11-25T01:07:38.361Z
updated_at: 2026-11-25T02:42:21.233Z
started_at: 2026-11-25T01:08:45.321Z
closed_at: 2026-11-25T02:42:21.233Z
close_reason: "Fixed in ea97d252d on PR #801 (review A dispositions: https://github.com/jlevy/metabrowser/pull/801#issuecomment-7151064403); A1's remaining shape is mb-q9ar, A6's Swift audit is mb-dhiw. CI run 45533955537 passed."
resolution: null
duplicate_of: null
---
Low finding A7 of review A on PR #801 (https://github.com/jlevy/metabrowser/pull/801#pullrequestreview-6049962996). References: static/plugin-sdk-views.js:1158, :1177-1181; static/source-pin-guard.js:123; static/source-ref-selector.js:935.
