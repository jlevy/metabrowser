---
type: is
id: is-01m2h5an32kbkp6zfkhkjzq55f
title: "GitHub Phase 3: bounded gh API transport and auth workflow"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h3vtmk6apasv27t6ygrrxf
  - type: blocks
    target: is-01m2h7gjbhrb9fdsbjjbcsf2n1
parent_id: is-01m10xd666fefs5z7ft5m58zj0
created_at: 2026-09-14T23:51:36.278Z
updated_at: 2026-09-15T00:29:47.247Z
---
Define the provider transport port and implement its only v0.11 transport with explicit, bounded gh api REST/GraphQL calls. Add gh auth status preflight without token display; explicit github.com or enterprise hostname selection; typed missing-cli, missing-login, insufficient-scope, permission, rate-limit, network, malformed-output, timeout, and cancellation states; and a copyable gh auth login recovery command that never runs interactively on a request path. Use a no-shell bounded process runner, one page per request, capped stdout/stderr, and sanitized logging. Do not use gh pr presentation output, gh --paginate, gh --cache, or durable raw responses. Record measurements and the rationale for deferring a direct-HTTP adapter.
