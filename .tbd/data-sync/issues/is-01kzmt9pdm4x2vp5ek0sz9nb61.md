---
type: is
id: is-01kzmt9pdm4x2vp5ek0sz9nb61
title: "PR #24 review R4: Preserve operational Git errors"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzmt94z25m0p0e3g531krnzy
created_at: 2026-08-10T03:08:42.803Z
updated_at: 2026-08-10T03:46:30.108Z
closed_at: 2026-08-10T03:46:30.108Z
close_reason: Fixed in 177e10f and 195b3e1; make verify and GitHub CI passed; all PR review threads replied to and resolved
---
Return 404 only for unknown revisions and map other GitError subclasses correctly; src/metabrowser/git/routes.py:163; thread PRRT_kwDOTX174c6XusNX.
