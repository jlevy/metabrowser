---
type: is
id: is-01m82s7wz42rxfvj0gc572kmt6
title: "PR #709 A5: record with no ETag makes the first probe answer changed and start a second full refresh"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82s73za15hfvfw96fdn9e19
created_at: 2026-11-22T23:25:12.006Z
updated_at: 2026-11-22T23:45:14.810Z
closed_at: 2026-11-22T23:45:14.787Z
close_reason: "fixed in aebc9cbb9: a path with no ETag is probed unconditionally and compared, and its ETag kept; test fails on 53ded9dbc"
resolution: null
duplicate_of: null
---
Medium. pulls.py probe_pull_request; cold read is GraphQL. https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6015073163
