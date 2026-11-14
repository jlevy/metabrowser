---
type: is
id: is-01m7dqmdjvjrgqd3vpqw3z3zdc
title: "Docs phase 2: the builder's path"
kind: feature
status: open
priority: 2
version: 9
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqm6j75a103hpze839wg7j
child_order_hints:
  - is-01m7dqrc33kxhve8xyrs14eqv3
  - is-01m7dqrchg7p9rh98mpsqyxezs
  - is-01m7dqrczwe5g7q2c8ja0vbz94
  - is-01m7dqrde8130517akbvnbters
  - is-01m7dqrdwsgt9p47d19rs6349h
  - is-01m7dqrebqet1yrb4fk82y9apg
  - is-01m7dqret6mea79taytx6m775k
  - is-01m7dqrf8f7b7qmw4f5ks1002v
created_at: 2026-11-14T19:13:02.042Z
updated_at: 2026-11-14T19:15:14.830Z
---
Phase 2 of the documentation plan: one stack of eight pull requests, stacked on phase 1. Architecture documents for every layer (CLI, server, inventory provider and Python engine, live delivery, Git, sources, diff, repository cache, mirrors, GitHub, plugins, browser shell, macOS app), the design and contributor documents, the map and entry point, and the project records. Copy-then-delete rule: the pull request that creates a destination copies material in; the owner of the source deletes it later in the stack. The fdu swap must touch only the engine document, the benchmark, the provider status line, and development.md's provider section.
