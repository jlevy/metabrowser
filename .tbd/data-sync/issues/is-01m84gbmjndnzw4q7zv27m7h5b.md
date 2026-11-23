---
type: is
id: is-01m84gbmjndnzw4q7zv27m7h5b
title: "Guided Review across a stack: one review order spanning the stack's pull requests"
kind: feature
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7x3g8rdhbeh7f0j0j7nz4sq
created_at: 2026-11-23T15:28:26.153Z
updated_at: 2026-11-23T16:18:52.915Z
---
Stacked pull requests split one change across several PRs, each with its own description and comparison. Design how a guide works across a stack: where the guide lives, how steps cite another layer's comparison, how staleness is judged per layer, and how the page moves between layers. Proposal first, for the user's decision.

## Notes

Proposal (2026-11-23, for the user's decision):
1. Each layer keeps its own guide, pinned to its own comparison (layer base -> layer head). Nothing new in Collection/v1; a layer's guide stays valid on GitHub alone.
2. The stack's guide is composed, not authored: on a PR in a stack, the step list groups every layer's overview and steps in stack order (bottom first), each named '#723 Step 2: title'. A layer with no guide shows as one entry, its description.
3. The arrows and the way on cross layer boundaries: past a layer's last step goes to the next layer's overview at /pull/<n>/guided, so each step gets an address (/pull/<n>/guided/<step>), which also makes a step linkable.
4. Staleness stays per layer, from that layer's pins; the stack list marks stale layers. A restack moves every layer's pins, so the notice names which layers moved.
5. Deferred: a reference citing another layer's diff ({pull: 723, path, ...}). Add only when a guide needs it.
Phases: (a) step addresses, (b) stack-composed list and cross-layer arrows, (c) per-layer staleness in the list.
