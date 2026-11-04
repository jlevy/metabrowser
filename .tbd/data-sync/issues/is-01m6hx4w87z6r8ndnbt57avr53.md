---
type: is
id: is-01m6hx4w87z6r8ndnbt57avr53
title: Show optional native PR stack membership and consistent loading skeletons
kind: feature
status: closed
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6hx7pwk8v4vt4tgmwvrn9fp
  - is-01m6hxmmmtnemb4656ebq7c7h4
  - is-01m6hxmn05jk5t44nvq1rans25
  - is-01m6hyepsg0bryhdsbn1fkre3b
  - is-01m6j2pt25zs6m77svjkrkhk5y
  - is-01m6j331jhmbnr4wdhjpf03pvs
hold: null
hold_until: null
created_at: 2026-11-03T23:50:40.131Z
updated_at: 2026-11-04T17:14:30.843Z
started_at: 2026-11-03T23:52:53.279Z
closed_at: 2026-11-04T17:14:30.843Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Owner explicitly requests implementing optional native GitHub stack numbers/UI in a new stacked PR above the current catalog/setup/performance work. Consult tbd gh-stack setup guidance, installed extension behavior and official API/source; use authoritative native membership, never infer a stack number from base branches. Display stack membership/navigation when tooling/API is available; gracefully omit optional enrichment otherwise without blocking normal PR data. Keep cache-only GETs and bounded background work, no per-row process/query storm or mutating gh stack commands in runtime. Also replace PR loading spinners with existing gray pulsing skeleton blocks aligned with the design system. Update setup/architecture/QA documentation and concise session goldens; independent review and final installed-wheel acceptance required. Preserve forward-only history and owner-only merge decision.
