---
type: is
id: is-01m35tapm6wjnn235hr3s669b7
title: Execute v0.12 direct-PR alpha acceptance on installed artifacts and a real browser
kind: task
status: in_progress
priority: 1
version: 7
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
updated_at: 2026-10-01T00:13:55.197Z
started_at: 2026-09-23T01:37:28.312Z
---
Execute the v0.12 alpha acceptance (T0-T2, thin-mirror scope) on an installed wheel and a real browser per docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md; the record is docs/project/qa/qa-2026-09-24-v012-alpha-acceptance.md. Ran 2026-09-24 with a rerun on #243. Remaining: rerun M03b and M08b after mb-zb5t lands; record M10 private and revoked as blocked (no operator-owned private fixture) unless the user supplies one. M10b, M12 and M13 are deferred by the user's 2026-09-23 decision and are not run. Does not merge or release.

## Notes

The walkthrough now explicitly exercises binding a disposable checkout, changing its remote, rejecting automatic identity reassignment, and using the planned explicit rebind operation without presenting old snapshots as new content. Feature implementation remains open; this tracking edit is not execution of T1/T2 acceptance.

2026-09-24 acceptance run (T1/T2, thin-mirror scope) on the integrated stack, PR #241 (merges #236, #238, #239 above #240), installed wheel, built-in browser. Record: docs/project/qa/qa-2026-09-24-v012-alpha-acceptance.md. Pass: M01, M02a, M03a, M04-M06, M07-M09, M10 (missing repo/PR, gh missing, signed out, gh too old), M11, and all round-2 features. Deferred by decision: M10b, M12, M13. Blocked: M10 private/revoked (no private fixture). Findings mb-ddbe (P2), mb-tals, mb-5wqg fixed in PR #243; rerun on #243 head 7d91c8f4 passed (section "Rerun on #243"). New P4s: mb-v8sb, mb-1bpe. Open: M03b/M08b await the user's decision on mb-zb5t. Keep open until that decision and the private-fixture row are dispositioned.
