---
type: is
id: is-01m2kb4fa0swgkhrvw3qq21gtq
title: "Hosted review Phase 0B.1e: model provider binding and hosted repositories"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b1
dependencies:
  - type: blocks
    target: is-01m2kb505pj16mgj8secgn4dex
  - type: blocks
    target: is-01m2kb5g8pf551djgfmf9kcm87
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:11:34.079Z
updated_at: 2026-09-15T20:12:07.829Z
---
Add ProviderBinding, RepositoryVisibility, HostedRepository, validate/dump entry points, and validate_repository_successor() to hosted_review/models.py. Keep binding auth-independent and limited to generic entry ID plus RepositoryRef and optional typed provenance. Make ProviderObjectRef(kind=repository) the repository identity authority; define or remove any domain ID duplication. Allow owner/name/default-branch/URL changes across renames while rejecting opaque repository identity changes or silent rebinding. Cover provider-neutral merge-request hosts, HTTPS URLs, canonical timestamps, hostile display strings, and closed-key rejection.
