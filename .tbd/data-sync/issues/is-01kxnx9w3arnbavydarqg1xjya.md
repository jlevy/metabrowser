---
type: is
id: is-01kxnx9w3arnbavydarqg1xjya
title: Add browser-grade DOM and payload contract coverage
kind: task
status: closed
priority: 2
version: 5
spec_path: TODO.md
labels:
  - browser
  - testing
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:49:05.129Z
updated_at: 2026-11-20T19:15:56.960Z
closed_at: 2026-11-14T18:44:04.468Z
close_reason: "Superseded: lifecycle and disposal coverage is the functional UI parity plan's mb-wgka (browserless production-JS sessions plus targeted Chrome tests), and payload contracts are the API schema plan's mb-xzb1 and mb-qdr1."
resolution: canceled
duplicate_of: null
extensions: {}
---
Add real DOM and browser smoke coverage for plugin lifecycle, selection, rendering, and disposal, plus generated or validated TypeScript contracts for backend payloads. Keep the fast Node VM contract tests while covering behavior that shims cannot prove.
