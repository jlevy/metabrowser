---
type: is
id: is-01m7n8yxeyv43vdked3pxpcveg
title: npm audit fails on GHSA-fc5q-39xc-vjpf (picomatch ReDoS) via tryscript
kind: bug
status: closed
priority: 1
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/523
    at: 2026-11-20T17:02:37.753Z
labels:
  - linear
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
created_at: 2026-11-17T17:30:32.798Z
updated_at: 2026-11-20T19:13:19.479Z
closed_at: 2026-11-18T01:19:30.944Z
close_reason: "Duplicate of mb-p1o0: tryscript 0.4.0 landed on main in jlevy/metabrowser#538, removing tinyglobby/fdir/picomatch and the GHSA-fc5q-39xc-vjpf path."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 03ac59c1-ce3a-43e0-9d38-7eb7ac3198b8
    linked_at: 2026-11-20T18:00:02.170Z
---
Since about 2026-11-17 17:00 UTC the lint job's 'make audit' step fails on every open PR (seen on jlevy/metabrowser#515, #517, #519, #520): npm audit reports 4 high-severity findings for picomatch (GHSA-fc5q-39xc-vjpf, ReDoS through single-branch repeated extglobs), reached as tryscript@0.3.1 -> tinyglobby@0.2.17 -> fdir@6.5.0/picomatch@4.0.7. picomatch 4.0.7 is the newest published release, so there is no patched version to take, and npm audit's only offered fix is downgrading tryscript to 0.2.1 (breaking). main's last CI (4eb299fd, 16:40Z) predates the advisory. Needs a decision per SUPPLY-CHAIN-SECURITY.md: a recorded, package-scoped audit exception for this advisory (picomatch is used only by the dev-time golden runner over repository-controlled globs), or wait for an upstream fix.
