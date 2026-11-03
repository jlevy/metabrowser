---
type: is
id: is-01m6hxmn05jk5t44nvq1rans25
title: Replace cold PR detail spinner with shared loading skeletons
kind: feature
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: pulls_navigation
labels: []
dependencies: []
parent_id: is-01m6hx4w87z6r8ndnbt57avr53
hold: null
hold_until: null
created_at: 2026-11-03T23:59:16.995Z
updated_at: 2026-11-03T23:59:29.644Z
started_at: 2026-11-03T23:59:29.644Z
---
Use existing gray pulsing skeleton tokens and loading delay for genuinely cold/pending PR detail. Keep cached PR data readable during refresh; no skeleton on absent/setup/error outcomes. Preserve accessible loading name, reduced-motion treatment and reading-column geometry. Review actual loading states, add targeted session coverage and regenerate truthful affected goldens.
