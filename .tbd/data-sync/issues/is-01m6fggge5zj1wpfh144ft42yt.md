---
type: is
id: is-01m6fggge5zj1wpfh144ft42yt
title: "PR #284 C4: a store answer depends on the reader global attributes file"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:20.901Z
updated_at: 2026-11-03T02:31:09.324Z
closed_at: 2026-11-03T02:31:09.323Z
close_reason: "C4 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 5609a0b6: HOME, XDG_CONFIG_HOME and GIT_ATTR_NOSYSTEM isolated for store reads; info/attributes in the token; test and probe."
resolution: null
duplicate_of: null
---
Medium. Review C https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745841338. git/process.py:160-170,504-506. GIT_ATTR_NOSYSTEM=1, HOME and XDG_CONFIG_HOME isolated in STORE_READ_POLICY and BATCH_OBJECT_POLICY.
