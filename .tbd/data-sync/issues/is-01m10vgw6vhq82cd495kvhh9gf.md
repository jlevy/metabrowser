---
type: is
id: is-01m10vgw6vhq82cd495kvhh9gf
title: "Hosted review Phase 0: provider-neutral format and SoftSchema corpus"
kind: feature
status: open
priority: 1
version: 17
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
  - type: blocks
    target: is-01m2h9jm62mjccx6x3bx0nct2a
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T05:36:41.690Z
updated_at: 2026-09-15T01:31:32.160Z
---
Define the no-network provider-neutral Hosted Review Format and plugin boundary. Model ProviderBinding, stable AuthorizationContextRef separate from volatile retrieval observations, transaction/sync manifests, HostedRepository, query-keyed ChangeRequestIndex with remote consistency, ChangeRequest, distinct ChangeRequestComment, Review, ReviewThread, ReviewComment, tagged file/line/range ReviewAnchor, Check, CommitStatus, RepositoryActivity, tombstone proof, and Git refs as closed contracts. Use frontmatter-md for change requests, reviews, and prose comments; YAML is machine authority and Review/v1 has an optional Markdown summary body. Compile SoftSchema, implement Python and browser validators for every browser-consumed record, and add body/no-body review fixtures, normalized/invalid and hostile-metadata fixtures, plus the scrubbed GitHub coverage oracle. Future GitLab is a named consumer; issues mb-9rrc and stacks mb-glxc remain later.
