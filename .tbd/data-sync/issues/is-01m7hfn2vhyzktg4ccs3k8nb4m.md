---
type: is
id: is-01m7hfn2vhyzktg4ccs3k8nb4m
title: "PR #470 A5: the Changes diff's first render validates the whole comparison twice"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjv212191g3nw3tr8take
hold: null
hold_until: null
created_at: 2026-11-16T06:10:32.944Z
updated_at: 2026-11-16T06:58:50.502Z
started_at: 2026-11-16T06:42:52.300Z
closed_at: 2026-11-16T06:58:50.501Z
close_reason: "Fixed in 71b51dc: summary validates with validateManifest; confirmed by route and model checks. Disposition reply: https://github.com/jlevy/metabrowser/pull/470#issuecomment-6909694363"
resolution: null
duplicate_of: null
---
diff/index.js:455, :513-514; pull-page.js:5427. summary validates the whole document, patches included. Severity: Low. PR #470, review A round 1: https://github.com/jlevy/metabrowser/pull/470#pullrequestreview-5915665462
