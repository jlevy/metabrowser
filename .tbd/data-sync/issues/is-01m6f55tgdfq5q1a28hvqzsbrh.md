---
type: is
id: is-01m6f55tgdfq5q1a28hvqzsbrh
title: Serving a new pull request goes silent after saying it is starting the server
kind: bug
status: closed
priority: 2
version: 4
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T22:13:16.426Z
updated_at: 2026-11-04T17:14:29.560Z
closed_at: 2026-11-04T17:14:29.560Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Found 2026-11-02. After a first clone, stderr says it is starting the server, then nothing for about 11 s while the PR is read, 17 s in total to the Serving line. A new PR on a cached mirror is silent for about 7 s. Say what is happening: a line naming that the pull request is being read, on the same cadence as clone progress. The performance study covers whether that time can also shrink.

## Notes

2026-11-03: fixed on PR 284 (ace33775): serving a pull request with no record says 'reading pull request N' after half a second. Reviewed in rounds 1 to 3. Closes when the stack merges.
