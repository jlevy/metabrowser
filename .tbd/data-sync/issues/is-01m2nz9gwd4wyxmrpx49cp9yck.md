---
type: is
id: is-01m2nz9gwd4wyxmrpx49cp9yck
title: Attach user-owned Git repositories to shared provider mirrors
kind: feature
status: deferred
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T20:42:19.915Z
updated_at: 2026-09-23T07:37:24.003Z
started_at: 2026-09-16T21:12:28.713Z
---
Enable hosted capabilities for an ordinary user-owned Git checkout without converting or copying it into a managed repository entry. Discover credential-free provider remote candidates read-only; resolve an unambiguous candidate through the provider registry to stable RepositoryRef; require explicit selection for multiple GitHub remotes and fork/upstream ambiguity; attach the session without persisting its absolute path; reuse the global provider mirror and lazily create or hydrate the shared repository store only for branch, diff, or PR content. Derive the canonical RepositoryStoreId deterministically from provider kind, canonical instance, raw stable repository opaque ID, and Git object format; converge verified objects and aliases under ordered locks and CAS without a mutable provider-to-store pointer. Prove no writes to files or .git, two local clones plus HTTPS/SSH sources reuse one provider repository and canonical store under the same auth context, different auth contexts remain isolated, failed convergence leaves aliases unchanged, purge/detach preserves shared reachable state, and local dirty state remains a filesystem overlay rather than mirror input.
