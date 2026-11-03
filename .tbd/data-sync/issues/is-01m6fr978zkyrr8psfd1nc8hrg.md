---
type: is
id: is-01m6fr978zkyrr8psfd1nc8hrg
title: "PR #284 D2: the store's memory is keyed without the token, so an info/attributes edit answers the old body under the new token"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fr829v5p0bx9wm4rr3z5wj
hold: null
hold_until: null
created_at: 2026-11-03T03:47:10.750Z
updated_at: 2026-11-03T03:53:08.949Z
started_at: 2026-11-03T03:47:30.586Z
closed_at: 2026-11-03T03:53:08.948Z
close_reason: |
  fixed in e610ebab: the store token is in the memory key; test_a_readers_global_attributes_do_not_reach_a_store holds one ComparisonCache across the edit (failed before, passes after); review D's Chrome scenario S3 replays correct.
resolution: null
duplicate_of: null
---
High. sidekick.py:322-345: kept_key and answer_key did not carry store_tag, so one process answered the old body, immutable, at the new address after an info/attributes edit; reproduced by review D in Chrome (S3). Same as Qodo https://github.com/jlevy/metabrowser/pull/284#discussion_r4450318489 and https://github.com/jlevy/metabrowser/pull/283#discussion_r4450564201. Fix: the token is in _kept_key; pinned with one ComparisonCache across the edit in tests/test_diff_comparison_cache.py.
