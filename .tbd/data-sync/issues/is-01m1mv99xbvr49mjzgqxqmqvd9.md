---
type: is
id: is-01m1mv99xbvr49mjzgqxqmqvd9
title: "PR #101 R5f: two arithmetic slips in the review doc performance table"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:22.218Z
updated_at: 2026-09-04T02:07:14.645Z
closed_at: 2026-09-04T02:07:14.644Z
close_reason: Fixed on claude/inventory-engine-perf; make verify green.
resolution: null
duplicate_of: null
---
The '1,887 ms | 1.11x slower' row is computed against exp-023's 1,705 ms interleaved control but sits in a column whose stated main baseline is 2,071 ms; two baselines share one column unannotated. '11.3% by median' appears to be the by-minimum figure (exp-023 records 8.2% by median). The PR title's 'close the regression' overstates its own documents.
