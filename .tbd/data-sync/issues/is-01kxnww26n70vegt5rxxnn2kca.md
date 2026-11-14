---
type: is
id: is-01kxnww26n70vegt5rxxnn2kca
title: Ratchet remaining Python strict-type debt
kind: chore
status: open
priority: 3
version: 7
spec_path: TODO.md
labels:
  - tooling
  - types
  - ratchet
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:41:32.628Z
updated_at: 2026-11-14T18:45:08.230Z
extensions:
  linear:
    id: 8fc405b1-c150-4848-aa57-4bf7f1046655
    linked_at: 2026-08-16T08:05:52.368Z
---
Continue removing the scoped BasedPyright exceptions without weakening the global strict floor. pyproject.toml's [tool.basedpyright] keeps typeCheckingMode = "strict" and scopes the debt to two executionEnvironments: src (reportPrivateUsage, reportUnknownArgumentType, reportUnknownMemberType, reportUnknownVariableType and reportUnusedFunction off) and tests (the pytest fixture and monkeypatch boundaries). devtools has none. Acceptance: turn a rule back on for an environment once its diagnostics reach zero, and never add a broad global suppression. Measure what remains by running basedpyright with the rule enabled rather than recording a count here.

## Notes

Baseline established after removing all broad global suppressions and eight removable source diagnostics. pyproject.toml scopes only the measured source and test debt; devtools remains fully strict. devtools/npm_policy.py rejects global regressions and pins the reviewed execution environments. Full release gate passes.
