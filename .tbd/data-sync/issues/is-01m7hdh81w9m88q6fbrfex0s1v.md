---
type: is
id: is-01m7hdh81w9m88q6fbrfex0s1v
title: "PR #465 A2: catalog rows persist a label color nothing reads, at the cost of a projection bump and a full rescan"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjnnynpvyk66k6knhg5vq
hold: null
hold_until: null
created_at: 2026-11-16T05:33:30.038Z
updated_at: 2026-11-16T06:22:48.960Z
started_at: 2026-11-16T05:33:41.238Z
closed_at: 2026-11-16T06:22:48.960Z
close_reason: "Fixed in e5b51e889: Keep bare names in rows. PullListLabel, color in the catalog query, and the CATALOG_PROJECTION bump dropped; record and core changes kept; row goldens and recording regenerated and equal to the base. No upper layer (origin/claude/label-color-cache, origin/claude/diff-summary-expand) reads row colors or bumps CATALOG_PROJECTION past 3. PR #465 review A2."
resolution: null
duplicate_of: null
---
Medium, PR #465 review A (https://github.com/jlevy/metabrowser/pull/465#pullrequestreview-5915428037). PullListLabel (pull_list.py:107-115, :141-143), color in the catalog query (pull_list_refresh.py:104, :170-181), CATALOG_PROJECTION = 3 (pull_catalog.py:64-66). No reader in this layer or above. Fix (coordinator): Keep bare names in rows, unless an upper layer reads row colors.
