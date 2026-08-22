---
type: is
id: is-01m0nvhcnmngzvd44djvb327rf
title: "PR #66 review F7: _git_ignored respawns an invariant git call per directory"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m0nvgqxqbb35etfxh3xbbkh9
created_at: 2026-08-22T23:05:19.795Z
updated_at: 2026-08-22T23:16:36.401Z
closed_at: 2026-08-22T23:16:36.400Z
close_reason: "Fixed: git rev-parse --local-env-vars hoisted into an lru_cache(maxsize=1) helper, halving the spawns per walked directory."
---
devtools/public_hygiene.py:116,169. _git_ignored runs 'git rev-parse --local-env-vars' AND 'git check-ignore' on every call, now once per walked directory. Measured 76 calls / 670 paths / 0.19s here so not a regression, but --local-env-vars is invariant. Fix: hoist it into a module-level cache; halves the spawns for free.
