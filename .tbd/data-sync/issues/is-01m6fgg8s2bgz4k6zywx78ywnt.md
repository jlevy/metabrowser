---
type: is
id: is-01m6fgg8s2bgz4k6zywx78ywnt
title: "PR #284 A3: comparison URL spelled in two plugins with nothing pinning them equal"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:13.057Z
updated_at: 2026-11-03T02:31:02.562Z
closed_at: 2026-11-03T02:31:02.561Z
close_reason: "A3 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 0aa8f047: the diff view's prefetch spells the one address; test_the_comparison_address_is_spelled_by_the_diff_plugin_alone."
resolution: null
duplicate_of: null
---
Medium. Review A https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745572379. github/pull-page.js:1856-1867, diff/index.js:38-53. One builder shared by both; pin equality.
