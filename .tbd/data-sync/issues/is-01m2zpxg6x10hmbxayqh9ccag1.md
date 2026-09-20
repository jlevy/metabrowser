---
type: is
id: is-01m2zpxg6x10hmbxayqh9ccag1
title: "S136-1: a broken third-party capability entry point poisons built-in validation; digest check is a no-op; duplicate inventory projection"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr136
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:21.720Z
updated_at: 2026-09-20T16:59:46.062Z
closed_at: 2026-09-20T16:59:46.060Z
close_reason: "Fixed on stab/s136 (pending integration into PR 136): 73efc9ee makes CapabilityRegistryError a RuntimeError so an installation failure is never reported as a record defect, and caches both outcomes; 7043e667 rewords the digest as identity; ef4e26a9 deletes the duplicate projection. Two regression tests red before, green after; 172 focused tests pass."
resolution: null
duplicate_of: null
---
Finding S136-1 from the v0.11 stabilization review. Owning layer: PR #136. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S136-1.
