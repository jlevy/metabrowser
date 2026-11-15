---
type: is
id: is-01m7g5yrx2z5bck8g4p1y4g6rx
title: Design-system consistency pass over this round's changes
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T18:01:50.241Z
updated_at: 2026-11-15T18:01:50.241Z
---
The user's request (2026-11-15), verbatim: "Let's make all of these consistent design system changes too, so everything is following standard conventions."

A consistency pass over everything this round changed, once it has landed on the stack: Show ignored on the Files row (mb-x1h6), the timeline run spacing (mb-xz1r), the Pulls nav rows and the dropped Stacks toggle (mb-vmwh, mb-ghff, mb-dzsi), the icon slots (mb-hmv7), the PR page header (mb-fon5, mb-4ydo, mb-cf0l), and bold PR numbers (the bead for that).

Done when a reviewer has checked each change against docs/design-system.md: it uses existing tokens and shared classes rather than local literals or one-off weights, sizes or spacings; it is stated once in the right section rather than repeated; and the sections that describe the old layout no longer do. Every inconsistency is fixed in the layer that introduced it, or filed as a bead with a reason.
