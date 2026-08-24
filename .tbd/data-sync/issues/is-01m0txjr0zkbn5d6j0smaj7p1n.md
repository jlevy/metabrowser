---
type: is
id: is-01m0txjr0zkbn5d6j0smaj7p1n
title: "PR #74 review MB74-C5: distinguish consumer reset from provider watch-gap recovery"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0txhaybmj82ym2wcm85zz0b
created_at: 2026-08-24T22:17:13.502Z
updated_at: 2026-08-24T22:25:27.199Z
---
Source: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5401198953. docs/project/architecture/arch-inventory-provider.md:187-200 needs to distinguish a consumer cursor reset (coherent reread) from provider observation overflow (stale answers while provider reconciliation re-verifies the affected scope), including coordinator expectations that avoid interpreting reconciliation as provider failure.
