---
type: is
id: is-01m2h3vtmk6apasv27t6ygrrxf
title: "GitHub Phase 3: selected PR and index cache slices"
kind: feature
status: closed
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m10xd666fefs5z7ft5m58zj0
child_order_hints:
  - is-01m2h7h50h2y8hhhq7x7f1zcmd
  - is-01m2h7hrjfx06hzpr7ptz7k9wn
created_at: 2026-09-14T23:26:01.873Z
updated_at: 2026-10-01T00:13:20.216Z
closed_at: 2026-10-01T00:13:20.212Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacements: mb-nkmq (PR #232, gh runner and PR records) and mb-vrl7 (PR #233, PR page). Binding, auth-scoped snapshots, leases and provider SDKs are retired. Deferred children mb-lnkl, mb-iw1v and mb-rldc moved to mb-k7zy."
resolution: canceled
duplicate_of: null
---
Umbrella for additive provider-cache delivery over mb-i3xc. First mb-h64t hydrates one directly addressed PR bundle and selected refs without an index. Then mb-lnkl adds a query-keyed bounded ChangeRequestIndex whose rows exclude review/check summaries and fetch no Git refs. Both scope pointers and validators by AuthorizationContextRef, publish only structurally valid committed manifests, keep partiality explicit with last-complete fallback, retain typed failures and offline reuse, and never persist raw responses or credentials.
