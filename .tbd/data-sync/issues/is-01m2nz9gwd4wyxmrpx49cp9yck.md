---
type: is
id: is-01m2nz9gwd4wyxmrpx49cp9yck
title: Attach user-owned Git repositories to shared provider mirrors
kind: feature
status: in_progress
priority: 1
version: 2
spec_path: docs/project/architecture/arch-repository-sources-and-provider-mirrors.md
delegate: codex@spud10
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T20:42:19.915Z
updated_at: 2026-09-16T21:12:28.713Z
started_at: 2026-09-16T21:12:28.713Z
---
Enable hosted capabilities for an ordinary user-owned Git checkout without converting or copying it into a managed repository entry. Discover credential-free provider remote candidates read-only; resolve an unambiguous candidate through the provider registry to stable RepositoryRef; require explicit selection for multiple GitHub remotes and fork/upstream ambiguity; attach the session without persisting its absolute path; reuse the global provider mirror and lazily create or hydrate the shared repository store only for branch, diff, or PR content. Prove no writes to files or .git, two local clones plus HTTPS/SSH sources reuse one provider repository under the same auth context, different auth contexts remain isolated, purge/detach preserves shared reachable state, and local dirty state remains a filesystem overlay rather than mirror input.
