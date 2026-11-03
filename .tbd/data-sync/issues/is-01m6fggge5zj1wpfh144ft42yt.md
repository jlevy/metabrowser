---
type: is
id: is-01m6fggge5zj1wpfh144ft42yt
title: "PR #284 C4: a store answer depends on the reader global attributes file"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:20.901Z
updated_at: 2026-11-03T01:31:20.901Z
---
Medium. Review C https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745841338. git/process.py:160-170,504-506. GIT_ATTR_NOSYSTEM=1, HOME and XDG_CONFIG_HOME isolated in STORE_READ_POLICY and BATCH_OBJECT_POLICY.
