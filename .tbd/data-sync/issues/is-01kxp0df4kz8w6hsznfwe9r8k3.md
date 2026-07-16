---
type: is
id: is-01kxp0df4kz8w6hsznfwe9r8k3
title: Simplify repository tooling policy into focused behavioral checks
kind: task
status: in_progress
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-07-16T17:43:28.658Z
updated_at: 2026-07-16T17:57:09.366Z
---

## Notes

Replaced the 425-line devtools/npm_policy.py with the shared 132-line devtools/check_supply_chain.py and focused tests. The checker now enforces only generic cross-file safeguards: .npmrc safety settings, exact direct npm specs, private package plus node/npm engines, matching nvm/fnm pins, registry+sha512 lock entries, uv 14-day cool-off, full-SHA actions, and minimal trusted publishing controls. Canonical configs own project versions, ratchets, build behavior, docs, and skills; Make/Lefthook/docs/spec references are updated. Checker and tests are byte-for-byte identical to KPress. Validation: targeted 4 tests; Ruff; BasedPyright; make format; full make verify with Node 24.18 via fnm (670 tests, audits clean, distribution and installed-wheel/plugin smoke passed). Ready for parent review and closure.
