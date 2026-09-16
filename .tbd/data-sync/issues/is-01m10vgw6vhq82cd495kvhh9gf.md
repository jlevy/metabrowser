---
type: is
id: is-01m10vgw6vhq82cd495kvhh9gf
title: "Hosted review Phase 0: provider-neutral format and SoftSchema corpus"
kind: feature
status: open
priority: 1
version: 34
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
child_order_hints:
  - is-01m2k1j7c9tf5d3b0aqxhf4mdk
  - is-01m2k1j89z4zp23fm2672tg92v
  - is-01m2k1j96v6f7pr5b6yxzc9xyt
  - is-01m2k1jazdf4m31f1vt80n858q
  - is-01m2k1jcp09qw704bx3hy87x9a
  - is-01m2k1jekxjs3avv8x3d1d60fv
  - is-01m2k1jg4afz39zgz5ktt49m2b
  - is-01m2k713pxra1ns2fk3pcwrpb6
  - is-01m2k1jj8edebds7zv8abfc917
  - is-01m2k1jkq9cvxx9db7a0z14b0z
  - is-01m2k1jnf5t6bgg340skd537hn
  - is-01m2k1jq7ydswdag1x08n30hvn
  - is-01m2k1jrywxceb6n3r0pbadegx
  - is-01m2nz8zzgxsw9yzsgekxy82sr
  - is-01m2nz98xx1f0js249srp1j39g
created_at: 2026-08-27T05:36:41.690Z
updated_at: 2026-09-16T20:42:11.772Z
---
Define the no-network provider-neutral Hosted Review Format and plugin boundary. Model ProviderBinding, stable AuthorizationContextRef separate from volatile retrieval observations, transaction/sync manifests, HostedRepository, query-keyed ChangeRequestIndex with remote consistency, ChangeRequest, distinct ChangeRequestComment, Review, ReviewThread, ReviewComment, tagged file/line/range ReviewAnchor, Check, CommitStatus, RepositoryActivity, tombstone proof, and Git refs as closed contracts. Use frontmatter-md for change requests, reviews, and prose comments; YAML is machine authority and Review/v1 has an optional Markdown summary body. Compile SoftSchema, implement Python and browser validators for every browser-consumed record, and add body/no-body review fixtures, normalized/invalid and hostile-metadata fixtures, plus the scrubbed GitHub coverage oracle. Future GitLab is a named consumer; issues mb-9rrc and stacks mb-glxc remain later.
