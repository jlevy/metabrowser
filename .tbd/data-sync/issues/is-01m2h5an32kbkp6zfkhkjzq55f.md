---
type: is
id: is-01m2h5an32kbkp6zfkhkjzq55f
title: "GitHub Phase 3: bounded gh API transport and auth workflow"
kind: task
status: open
priority: 1
version: 18
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
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
child_order_hints:
  - is-01m2p5vzgcbwexb62ep1mb2gjc
hold: null
hold_until: null
created_at: 2026-09-14T23:51:36.278Z
updated_at: 2026-09-23T00:21:40.947Z
started_at: 2026-09-16T22:03:44.738Z
---
Implement the only v0.11 provider transport with fixed gh api REST endpoint templates and checked-in GraphQL documents, explicit host/API-version/Accept profiles, and bounded JSON variables through --input -. After non-secret gh auth status preflight selects a login, open one broker-pinned GhCredentialSession, resolve its stable opaque principal ID through fixed /user, and run every endpoint and page for the acquisition through that same session. Request broker-registered GitFetchCredentialLease handles (mb-y1ax issuance, mb-jlon registry) for exact provider-declared credential-free HTTPS repository sources so selected Git refs use the same pinned principal and cannot fall back to ambient Git auth. A concurrent external gh auth switch, broker loss, token rejection, or lease mismatch aborts publication. Keep login/scopes as retrieval observations. Typed builders allowlist and percent-encode REST path components. Parse --include status and allowlisted headers separately; type GraphQL partial errors, nulls, malformed content, truncation, unsupported GHES, auth, permission, rate-limit, network, timeout, cancellation, and Git-credential-unavailable states. Never use raw untrusted arguments, -f/-F, gh pr output, --paginate, --cache, verbose output, interactive login, durable raw responses, or secret-bearing diagnostics.
