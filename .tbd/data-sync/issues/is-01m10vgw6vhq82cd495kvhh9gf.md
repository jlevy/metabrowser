---
type: is
id: is-01m10vgw6vhq82cd495kvhh9gf
title: "Hosted review Phase 0: provider-neutral format and SoftSchema corpus"
kind: feature
status: open
priority: 1
version: 14
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m10xd666fefs5z7ft5m58zj0
  - type: blocks
    target: is-01m2h3vtmk6apasv27t6ygrrxf
  - type: blocks
    target: is-01m2h5an32kbkp6zfkhkjzq55f
  - type: blocks
    target: is-01m0b71xwkrf39qnq9ccgxmfp4
  - type: blocks
    target: is-01m2h7gjbhrb9fdsbjjbcsf2n1
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T05:36:41.690Z
updated_at: 2026-09-15T00:29:47.247Z
---
Define the no-network format and plugin boundary for the v0.11 GitHub-first slice. Model ProviderBinding, retrieval and sync manifests, HostedRepository, ChangeRequestIndex, ChangeRequest, Review, ReviewThread, ReviewComment, Check, CommitStatus, RepositoryActivity, and Git object references as provider-neutral closed contracts. Use SoftSchema frontmatter-md for ChangeRequest, with consumed values in YAML and the PR description in the Markdown body; use pure-yaml for indexes, manifests, and compact companions. Add Pydantic and browser validators, compiled schemas, a terminology mapping matrix, normalized/invalid fixtures, and the scrubbed GitHub coverage oracle. GitHub is the first adapter; future GitLab is a named consumer, not a source of speculative fields. Issues remain mb-9rrc; stacked changes remain mb-glxc.
