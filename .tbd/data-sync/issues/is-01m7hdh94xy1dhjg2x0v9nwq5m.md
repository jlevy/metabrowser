---
type: is
id: is-01m7hdh94xy1dhjg2x0v9nwq5m
title: "PR #465 A3: two comments misstate the row's label data"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjnnynpvyk66k6knhg5vq
hold: null
hold_until: null
created_at: 2026-11-16T05:33:31.164Z
updated_at: 2026-11-16T06:22:49.338Z
started_at: 2026-11-16T05:33:42.097Z
closed_at: 2026-11-16T06:22:49.337Z
close_reason: "Fixed in e5b51e889: both comments reverted with A2; pull_catalog.py and pull_list_refresh.py equal the base. PR #465 review A3."
resolution: null
duplicate_of: null
---
Low, PR #465 review A (https://github.com/jlevy/metabrowser/pull/465#pullrequestreview-5915428037). pull_catalog.py:65 says projection 3 adds each label's color and description; pull_list_refresh.py:86 says the row's color is what its chip is painted by. Fix or revert with A2.
