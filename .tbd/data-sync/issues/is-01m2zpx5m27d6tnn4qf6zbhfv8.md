---
type: is
id: is-01m2zpx5m27d6tnn4qf6zbhfv8
title: Apply a forced untrusted profile to every acquired-source entrypoint
kind: feature
status: in_progress
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10
labels:
  - release:v0.12.0
  - stack:followup
dependencies:
  - type: blocks
    target: is-01m35tapm6wjnn235hr3s669b7
  - type: blocks
    target: is-01m36ma4er7sj7gqsqpz6jms30
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
hold: null
hold_until: null
created_at: 2026-09-20T15:28:10.881Z
updated_at: 2026-09-23T07:57:33.150Z
started_at: 2026-09-23T03:31:09.257Z
---
Finding S209-3 from the v0.11 stabilization review. Owning layer: PR #209. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S209-3.

## Notes

2026-09-22 (codex/v012-foundation-stabilization d99d0b9d): pin entry points done. --show and non-cache --api on a file:// pin always pass the untrusted profile as an explicit flag, so METAB_ACTIVE_CONTENT=1 and METAB_ALLOW_EDITS=1 cannot lift it, and --allow-edits is refused with a typed error. Tests (tests/test_cli_acquire.py): default, explicit, env-enables, env-trusted via /api/capabilities; --show; a pin in a populated cache sees only its own tree. Real CLI on Git 2.50.1 confirmed. Still open for the URL-opened roots and the HTTP server entry point, which are Phase 2A (mb-innz/mb-ew38). Keep open until then.

Earlier notes:
2026-09-22 reconciliation: the generic HTML trust foundation in #209 is merged and inherited by the current v0.12 stack. This remaining work is acquired-source integration on an additional PR above the stack, not reopening #209. Apply a non-overridable untrusted profile before pin/URL source use; prove every entrypoint and populated-cache isolation. It remains a blocker for the GitHub alpha acceptance in mb-gnr9.
