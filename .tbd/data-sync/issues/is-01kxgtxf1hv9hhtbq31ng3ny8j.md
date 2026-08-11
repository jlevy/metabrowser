---
type: is
id: is-01kxgtxf1hv9hhtbq31ng3ny8j
title: Wait for remote tunnel HTTP readiness
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
created_at: 2026-07-14T17:31:09.232Z
updated_at: 2026-07-17T21:16:40.620Z
closed_at: 2026-07-14T17:34:06.587Z
close_reason: Replaced remote's fixed delay with the shared cancellable HTTP-readiness probe used by serve, preserved portable browser error handling, updated docs/spec, and passed the full 598-test release gate plus clean npm audit.
---
Address PR #1 review finding: replace remote's fixed browser-open delay with the same HTTP readiness semantics used by serve. Extract one shared cancellable probe, preserve portable webbrowser handling, add regression coverage, and rerun the complete release gate.
