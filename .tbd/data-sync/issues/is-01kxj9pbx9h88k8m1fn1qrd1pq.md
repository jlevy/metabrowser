---
type: is
id: is-01kxj9pbx9h88k8m1fn1qrd1pq
title: Isolate npm commands from ambient release-cutoff configuration
kind: bug
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-15T07:08:39.718Z
updated_at: 2026-07-17T21:16:39.135Z
closed_at: 2026-07-15T07:17:34.054Z
close_reason: Make ignores conflicting ambient npm cutoff configuration, package policy enforces the boundary, nvm and fnm select Node 24.18.0, and the full release gate passes at c412d8c.
---
The release gate can fail before npm ci when a managed shell exports NPM_CONFIG_BEFORE together with the repository's min-release-age policy. Unexport the ambient cutoff in Make targets, preserve repository .npmrc policy, and validate the pinned Node setup through both fnm and nvm.

## Notes

Reproduced a release-gate failure when a managed shell exports NPM_CONFIG_BEFORE alongside the repository min-release-age setting. Make now unexports the conflicting ambient cutoff and package policy enforces the isolation. Both fnm use and nvm use select the checked-in Node 24.18.0 pin; full verification passes under fnm with npm 11.10.0.
