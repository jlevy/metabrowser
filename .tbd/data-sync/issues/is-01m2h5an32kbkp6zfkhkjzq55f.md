---
type: is
id: is-01m2h5an32kbkp6zfkhkjzq55f
title: "GitHub Phase 3: bounded gh API transport and auth workflow"
kind: task
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h3vtmk6apasv27t6ygrrxf
  - type: blocks
    target: is-01m2h7gjbhrb9fdsbjjbcsf2n1
  - type: blocks
    target: is-01m2ktpzzzg5crhj0ggx8bbt1t
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
parent_id: is-01m10xd666fefs5z7ft5m58zj0
created_at: 2026-09-14T23:51:36.278Z
updated_at: 2026-09-16T01:07:30.801Z
---
Implement the only v0.11 provider transport with fixed gh api REST endpoint templates and checked-in GraphQL documents, explicit host/API-version/Accept profiles, and bounded JSON variables through --input -. After non-secret gh auth status preflight, issue a fixed bounded /user request to resolve the stable opaque principal ID; keep login/scopes as retrieval observations and refuse authenticated publication if identity cannot be resolved. Typed builders allowlist and percent-encode required REST path components before one argv element. Parse --include status and allowlisted headers separately from the bounded body; type GraphQL data-plus-errors, null nodes, malformed content, truncation, unsupported GHES, auth, permission, rate-limit, network, timeout, and cancellation outcomes. Never use raw untrusted arguments, -f/-F, gh pr output, --paginate, --cache, verbose output, interactive login, durable raw responses, or secret-bearing diagnostics.
