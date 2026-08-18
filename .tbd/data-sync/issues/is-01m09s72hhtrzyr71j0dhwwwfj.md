---
type: is
id: is-01m09s72hhtrzyr71j0dhwwwfj
title: "Diff: decide the core/plugin split for hosted and document sources"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-18T06:33:51.408Z
updated_at: 2026-08-18T19:55:24.800Z
---
Refined by the Consumers and composition section of the spec: PR *refs* ride the git transport and belong to the core Git adapter (refs/pull/<n>/head and /merge are fetchable with no API — verified live). PR *conversation and metadata* (title, state, checks, review threads) is the true hosted-provider surface and belongs to a plugin. Remaining question: which Platform A1-A5 items that conversation plugin actually needs, scheduled against it as a real consumer rather than speculatively.
