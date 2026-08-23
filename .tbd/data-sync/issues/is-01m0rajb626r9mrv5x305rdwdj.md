---
type: is
id: is-01m0rajb626r9mrv5x305rdwdj
title: Expose console diagnostics through window.metabrowser
kind: feature
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-08-23T22:06:28.545Z
updated_at: 2026-08-23T22:36:49.941Z
closed_at: 2026-08-23T22:36:49.940Z
close_reason: Unified browser diagnostics under window.metabrowser, added contracts/types/docs, passed live smoke and make verify.
---
Make window.metabrowser the stable browser-console namespace, expose the performance diagnostics API as metabrowser.perf, enforce the contract in tests and types, and document the supported troubleshooting workflow.
