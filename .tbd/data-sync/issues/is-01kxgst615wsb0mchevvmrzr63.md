---
type: is
id: is-01kxgst615wsb0mchevvmrzr63
title: Reject duplicate plugin data-hook routes
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
created_at: 2026-07-14T17:11:53.125Z
updated_at: 2026-07-17T21:16:39.838Z
closed_at: 2026-07-14T17:14:18.440Z
close_reason: Rejected duplicate data-hook routes at manifest validation, documented the contract, and verified the complete 595-test release gate plus clean npm audit.
---
Address PR #1 review finding: reject duplicate [[data_hook]] routes in one plugin manifest so Starlette route ordering cannot silently make later handlers unreachable. Add manifest regression coverage and rerun release validation.
