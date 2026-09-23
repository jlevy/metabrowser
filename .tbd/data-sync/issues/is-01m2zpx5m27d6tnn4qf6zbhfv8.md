---
type: is
id: is-01m2zpx5m27d6tnn4qf6zbhfv8
title: Apply a forced untrusted profile to every acquired-source entrypoint
kind: feature
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10
labels:
  - release:v0.12.0
  - stack:followup
dependencies:
  - type: blocks
    target: is-01m35tapm6wjnn235hr3s669b7
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
hold: null
hold_until: null
created_at: 2026-09-20T15:28:10.881Z
updated_at: 2026-09-23T03:31:09.258Z
started_at: 2026-09-23T03:31:09.257Z
---
Finding S209-3 from the v0.11 stabilization review. Owning layer: PR #209. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S209-3.

## Notes

2026-09-22 reconciliation: the generic HTML trust foundation in #209 is merged and inherited by the current v0.12 stack. This remaining work is acquired-source integration on an additional PR above the stack, not reopening #209. Apply a non-overridable untrusted profile before pin/URL source use; prove every entrypoint and populated-cache isolation. It remains a blocker for the GitHub alpha acceptance in mb-gnr9.
