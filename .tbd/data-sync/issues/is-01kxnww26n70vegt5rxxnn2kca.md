---
type: is
id: is-01kxnww26n70vegt5rxxnn2kca
title: Ratchet remaining Python strict-type debt
kind: chore
status: open
priority: 3
version: 2
spec_path: docs/development.md
labels:
  - tooling
  - types
  - ratchet
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-16T16:41:32.628Z
updated_at: 2026-07-16T16:44:32.361Z
---
Continue removing the explicitly scoped BasedPyright legacy exceptions without weakening the global strict floor. The 2026-07-16 unsuppressed baseline is 483 diagnostics: 121 in src across private-helper usage, unknown arguments/members/variables, and unused nested functions; 362 at pytest fixture and monkeypatch boundaries. devtools has no scoped exception. Acceptance: reduce the measured counts, delete exception categories as they reach zero, keep typeCheckingMode=strict, and never add a broad global suppression.

## Notes

Baseline established after removing all broad global suppressions and eight removable source diagnostics. pyproject.toml scopes only the measured source and test debt; devtools remains fully strict. devtools/npm_policy.py rejects global regressions and pins the reviewed execution environments. Full release gate passes.
