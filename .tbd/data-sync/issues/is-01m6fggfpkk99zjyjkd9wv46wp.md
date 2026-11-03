---
type: is
id: is-01m6fggfpkk99zjyjkd9wv46wp
title: "PR #284 C2: the immutable address names no subject, so a folder replays a store answer"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:20.146Z
updated_at: 2026-11-03T01:31:20.146Z
---
High. Review C https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745841338. diff/index.js:36-52, pull-page.js:1856-1867, sidekick.py:291-301. Server-provided store token in the address; immutable only when it matches.
