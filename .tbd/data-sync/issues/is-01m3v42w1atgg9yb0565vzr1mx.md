---
type: is
id: is-01m3v42w1atgg9yb0565vzr1mx
title: "check_parity reads only tryscript blocks: let a row cite an in-process .txt golden as route evidence"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T06:57:58.810Z
updated_at: 2026-10-01T06:57:58.810Z
---
From the PR #253 review (mb-99pm): devtools/check_parity.py reads only tryscript console blocks, so a route whose successful invocation is shown honestly only by an in-process golden (for example /api/plugin/github/pull-refresh completing with a fake gh, in tests/test_cli_github_pull_golden.py) cannot cite it; #253 narrowed a special clause for that one route instead. Teach the gate to accept a named .txt golden command as evidence, with the same exact-route and exit-status rules, then remove the special clause. Not labelled v0.12: the narrowed clause is honest and tested.
