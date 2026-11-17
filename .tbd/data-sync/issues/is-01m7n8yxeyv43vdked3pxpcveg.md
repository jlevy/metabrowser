---
type: is
id: is-01m7n8yxeyv43vdked3pxpcveg
title: npm audit fails on GHSA-fc5q-39xc-vjpf (picomatch ReDoS) via tryscript
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-17T17:30:32.798Z
updated_at: 2026-11-17T17:30:32.798Z
---
Since about 2026-11-17 17:00 UTC the lint job's 'make audit' step fails on every open PR (seen on jlevy/metabrowser#515, #517, #519, #520): npm audit reports 4 high-severity findings for picomatch (GHSA-fc5q-39xc-vjpf, ReDoS through single-branch repeated extglobs), reached as tryscript@0.3.1 -> tinyglobby@0.2.17 -> fdir@6.5.0/picomatch@4.0.7. picomatch 4.0.7 is the newest published release, so there is no patched version to take, and npm audit's only offered fix is downgrading tryscript to 0.2.1 (breaking). main's last CI (4eb299fd, 16:40Z) predates the advisory. Needs a decision per SUPPLY-CHAIN-SECURITY.md: a recorded, package-scoped audit exception for this advisory (picomatch is used only by the dev-time golden runner over repository-controlled globs), or wait for an upstream fix.
