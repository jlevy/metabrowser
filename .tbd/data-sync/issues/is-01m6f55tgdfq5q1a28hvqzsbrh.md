---
type: is
id: is-01m6f55tgdfq5q1a28hvqzsbrh
title: Serving a new pull request goes silent after saying it is starting the server
kind: bug
status: in_progress
priority: 2
version: 3
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T22:13:16.426Z
updated_at: 2026-11-03T07:00:54.427Z
---
Found 2026-11-02. After a first clone, stderr says it is starting the server, then nothing for about 11 s while the PR is read, 17 s in total to the Serving line. A new PR on a cached mirror is silent for about 7 s. Say what is happening: a line naming that the pull request is being read, on the same cadence as clone progress. The performance study covers whether that time can also shrink.

## Notes

2026-11-03: fixed on PR 284 (ace33775): serving a pull request with no record says 'reading pull request N' after half a second. Reviewed in rounds 1 to 3. Closes when the stack merges.
