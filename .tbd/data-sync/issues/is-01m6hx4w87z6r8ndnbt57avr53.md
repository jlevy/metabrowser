---
type: is
id: is-01m6hx4w87z6r8ndnbt57avr53
title: Show optional native PR stack membership and consistent loading skeletons
kind: feature
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6hx7pwk8v4vt4tgmwvrn9fp
  - is-01m6hxmmmtnemb4656ebq7c7h4
  - is-01m6hxmn05jk5t44nvq1rans25
hold: null
hold_until: null
created_at: 2026-11-03T23:50:40.131Z
updated_at: 2026-11-03T23:59:16.995Z
started_at: 2026-11-03T23:52:53.279Z
---
Owner explicitly requests implementing optional native GitHub stack numbers/UI in a new stacked PR above the current catalog/setup/performance work. Consult tbd gh-stack setup guidance, installed extension behavior and official API/source; use authoritative native membership, never infer a stack number from base branches. Display stack membership/navigation when tooling/API is available; gracefully omit optional enrichment otherwise without blocking normal PR data. Keep cache-only GETs and bounded background work, no per-row process/query storm or mutating gh stack commands in runtime. Also replace PR loading spinners with existing gray pulsing skeleton blocks aligned with the design system. Update setup/architecture/QA documentation and concise session goldens; independent review and final installed-wheel acceptance required. Preserve forward-only history and owner-only merge decision.
