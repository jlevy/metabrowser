---
type: is
id: is-01kxnww26n70vegt5rxxnn2kca
title: Ratchet remaining Python strict-type debt
kind: chore
status: open
priority: 3
version: 5
spec_path: TODO.md
labels:
  - tooling
  - types
  - ratchet
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:41:32.628Z
updated_at: 2026-08-16T08:05:43.098Z
extensions:
  linear:
    id: 8fc405b1-c150-4848-aa57-4bf7f1046655
    linked_at: 2026-08-16T08:05:43.098Z
---
Continue removing the explicitly scoped BasedPyright legacy exceptions without weakening the global strict floor. The 2026-07-16 unsuppressed baseline is 483 diagnostics: 121 in src across private-helper usage, unknown arguments/members/variables, and unused nested functions; 362 at pytest fixture and monkeypatch boundaries. devtools has no scoped exception. Acceptance: reduce the measured counts, delete exception categories as they reach zero, keep typeCheckingMode=strict, and never add a broad global suppression.

## Notes

Baseline established after removing all broad global suppressions and eight removable source diagnostics. pyproject.toml scopes only the measured source and test debt; devtools remains fully strict. devtools/npm_policy.py rejects global regressions and pins the reviewed execution environments. Full release gate passes.
