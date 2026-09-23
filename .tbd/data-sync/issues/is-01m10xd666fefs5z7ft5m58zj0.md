---
type: is
id: is-01m10xd666fefs5z7ft5m58zj0
title: "GitHub Phase 3: gh adapter, binding, and provider snapshots"
kind: feature
status: in_progress
priority: 1
version: 21
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m10vgwqwn8gjdv8fm183vztr
  - type: blocks
    target: is-01m2h3wteafc7mt3x0efnv4xex
  - type: blocks
    target: is-01m2ktrc9jfznq2b0kh57e4735
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m2h3vtmk6apasv27t6ygrrxf
  - is-01m2h5an32kbkp6zfkhkjzq55f
  - is-01m2h7gjbhrb9fdsbjjbcsf2n1
  - is-01m2h9jka5t3kw909ae7xefx8d
  - is-01m2h9jm62mjccx6x3bx0nct2a
  - is-01m2kvemzp183vrykz849c0s5a
  - is-01m2kw2bvjj5kcsczkz40cmhqx
  - is-01m2kw2c5sak3agfksaqecefa5
  - is-01m2kw2cf1gxnanj6e1wyh6frw
hold: null
hold_until: null
created_at: 2026-08-27T06:09:37.988Z
updated_at: 2026-09-23T00:40:30.862Z
started_at: 2026-09-23T00:40:30.862Z
---
Implement the GitHub provider lane through three explicit foundations: bounded provider_process work, the mb-ji83 ProviderAdapterSpec capability/lifecycle registry, and the mb-i3xc auth-scoped provider-store kernel. The only v0.11 transport is hardened gh api with explicit host/auth outcomes. Bind repositories without changing generic identity and publish provider-neutral immutable records with distinct transaction/coverage state, current plus last-complete pointers, leases, and bounded reclamation. Depend on mb-63ym and mb-jlon, not full cache management; never persist raw responses or credentials.
