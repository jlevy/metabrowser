---
type: is
id: is-01m2h7gjbhrb9fdsbjjbcsf2n1
title: "GitHub Phase 3A: provider binding and repository summary snapshot"
kind: task
status: in_progress
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: codex@spud10
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
  - type: blocks
    target: is-01m2nz9gwd4wyxmrpx49cp9yck
parent_id: is-01m10xd666fefs5z7ft5m58zj0
hold: null
hold_until: null
created_at: 2026-09-15T00:29:47.247Z
updated_at: 2026-09-16T21:11:50.868Z
started_at: 2026-09-16T21:10:44.888Z
---
Bind a conservative credential-free source identity to a stable GitHub RepositoryRef without requiring a managed cache entry or persisting a local path. Discover GitHub through mb-ji83 and publish HostedRepository, Retrieval, and committed repository-summary manifests through the shared provider store. Permit many source IDs to map to one repository; reject conflicting rebinds; isolate auth-scoped pointers and validators; and revalidate source, repository, and auth identity after lock-free acquisition. Expose summary routes and CLI parity without raw responses or credentials.
