---
type: is
id: is-01m269p2k74jayrjt4vjad15y2
title: Enforce functional UI parity with CLI goldens
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md
labels: []
dependencies: []
created_at: 2026-09-10T18:36:06.117Z
updated_at: 2026-09-10T18:36:11.508Z
---
Replace the blanket view-layer exemption with a checked functional-aspect registry. Data semantics must be reachable through metab and nontrivially golden-pinned; browser-owned interaction semantics must run against exact production JavaScript in browserless CLI sessions; only paint/platform behavior may be explicitly exempt with a reason. Seed the mechanism with the Recent filtering regression and negative checker tests.
