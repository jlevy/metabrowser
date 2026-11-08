---
type: is
id: is-01m6ypyka1a299qkdhw8es07ps
title: Simplify contract namespaces and safely upgrade the owner configuration
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m5wdbsy6z6d95sgg03kwmm76
hold: null
hold_until: null
created_at: 2026-11-08T23:12:30.527Z
updated_at: 2026-11-08T23:25:04.185Z
started_at: 2026-11-08T23:12:31.097Z
---
Owner requested concise hosting-independent names: metabrowser.config:ApplicationConfig/v1 and metabrowser.cache:* instead of com.github.jlevy.metabrowser.*. This is alpha with no external users; only the existing owner account needs a smooth upgrade. Trace and document the origin/Softschema naming rule, update canonical constants, generated schemas, tests/goldens and relevant current examples, and implement the smallest safe one-time upgrade through the existing storage mechanisms. No permanent old-name aliases or speculative backward compatibility. Preserve unknown user settings/comments, private modes, cache identities and Git objects; atomic/idempotent writes and a narrow old-namespace migration boundary. On malformed/unreadable config, fail without traceback or overwriting it and print its location plus a clear instruction to move aside or remove config and restart to recreate it; repository cache remains intact. Track/review migration design before substantial edits. Use a new forward stack layer on reviewed/gated b2fb62099 (PR342); normal full gate/CI/independent review before account promotion. Actual account upgrade is explicitly authorized, but only after qualifying the new artifact and coordinating all four installed servers. Keep private config contents out of public output.

## Notes

November 8 release contract checkpoint: this blocker is implementation-in-progress, not delivered. The current qualified/installed b2fb predecessor passed its full gate and is published as stack #339 through #342; its final CI/actual merges remain separate. The user wants canonical metabrowser.config and metabrowser.cache identifiers with no shipped old aliases, f02 or permanent compatibility, retaining f01/v1 payloads. Malformed config needs exact path and move/remove/restart-to-recreate guidance, without traceback or cache loss. Read-only inventory found one config root, one cache root, 17 headers and valid config; no account writes. Explicitly authorized one-account alpha upgrade still needs independent review/gate; safer reversible delta-header journal is planned after automatic review rejected raw YAML duplication. No actual migration or raw backup is claimed. Parent mb-4bd2 depends on this blocker. Separate macOS spike #341 is outside this release and must not be added as a blocker. Preserve current delegate/status/dependencies; no closure before qualified delivery and actual merge.
