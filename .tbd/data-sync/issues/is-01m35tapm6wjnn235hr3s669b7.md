---
type: is
id: is-01m35tapm6wjnn235hr3s669b7
title: Execute v0.12 direct-PR alpha acceptance on installed artifacts and a real browser
kind: task
status: in_progress
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-23T00:23:26.596Z
updated_at: 2026-09-24T23:49:38.088Z
started_at: 2026-09-23T01:37:28.312Z
---
Run T1 and T2 acceptance from the alpha test plan after the corresponding implementation/publication beads complete. Exercise the installed wheel through real CLI and HTTP startup, GitHub repository/tree/blob/commit/raw/PR URL forms, a directly addressed PR absent from the index, cold/warm/offline behavior, two concurrent revisions, private authorization and typed failures, trust with populated cache, and browser navigation/rendering. Add deterministic adapter-to-store-to-view and production-JS golden coverage in each owning implementation PR; record exact head/base/main/tool versions and pass/fail/blocked for manual rows M01-M11, including M10b explicit provider rebind. T0 was exercised during mb-eegt but does not satisfy this future GitHub alpha. Keep the whole formal stack held until stabilization; this task does not merge or publish a release. No tbd release or optional shortcut cleanup gates these tests.

## Notes

The walkthrough now explicitly exercises binding a disposable checkout, changing its remote, rejecting automatic identity reassignment, and using the planned explicit rebind operation without presenting old snapshots as new content. Feature implementation remains open; this tracking edit is not execution of T1/T2 acceptance.

2026-09-24 acceptance run (T1/T2, thin-mirror scope) on the integrated stack, PR #241 (merges #236, #238, #239 above #240), installed wheel, built-in browser. Record: docs/project/qa/qa-2026-09-24-v012-alpha-acceptance.md. Pass: M01, M02a, M03a, M04-M06, M07-M09, M10 (missing repo/PR, gh missing, signed out, gh too old), M11, and all round-2 features. Deferred by decision: M10b, M12, M13. Blocked: M10 private/revoked (no private fixture). Findings mb-ddbe (P2), mb-tals, mb-5wqg fixed in PR #243; rerun on #243 head 7d91c8f4 passed (section "Rerun on #243"). New P4s: mb-v8sb, mb-1bpe. Open: M03b/M08b await the user's decision on mb-zb5t. Keep open until that decision and the private-fixture row are dispositioned.
