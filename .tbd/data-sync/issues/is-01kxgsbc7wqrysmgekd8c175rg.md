---
type: is
id: is-01kxgsbc7wqrysmgekd8c175rg
title: Resolve standalone plugin boundary review findings
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
created_at: 2026-07-14T17:03:47.964Z
updated_at: 2026-07-14T17:09:09.751Z
closed_at: 2026-07-14T17:09:09.750Z
close_reason: "Resolved all three PR #1 review findings with regression tests: server imports after CLI/dotenv configuration, documented callable entry-point factories are invoked, and operator-directory plugins cannot mount Python data hooks. make verify passes with 594 tests and npm audit reports zero vulnerabilities."
---
Address PR #1 review findings: defer server import until CLI configuration is applied, honor callable plugin entry points documented by the public API, and prevent operator-directory plugins from mounting Python data hooks. Add regression coverage and rerun the release gate.
