---
type: is
id: is-01m10xd666fefs5z7ft5m58zj0
title: "GitHub Phase 3: gh adapter, binding, and provider snapshots"
kind: feature
status: open
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m10vgwqwn8gjdv8fm183vztr
  - type: blocks
    target: is-01m2h3wteafc7mt3x0efnv4xex
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m2h3vtmk6apasv27t6ygrrxf
  - is-01m2h5an32kbkp6zfkhkjzq55f
created_at: 2026-08-27T06:09:37.988Z
updated_at: 2026-09-14T23:51:36.278Z
---
Implement the GitHub provider port for the v0.11 slice with one transport: bounded, cancellable gh api REST/GraphQL calls and explicit hostname selection. Add non-secret auth preflight plus typed missing-cli, missing-login, insufficient-scope, permission, rate-limit, network, malformed-output, and cancellation states; never show tokens, start interactive login on a request path, use gh --paginate/--cache, or persist raw responses. Bind repositories without changing generic cache identity and publish provider-neutral immutable Hosted Review Format snapshots, sync manifests, and atomic current pointers. This depends on mb-63ym and the narrow core job/ref foundation mb-jlon, not full cache management mb-0ybg.
