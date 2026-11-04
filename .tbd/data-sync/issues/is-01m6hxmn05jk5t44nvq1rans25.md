---
type: is
id: is-01m6hxmn05jk5t44nvq1rans25
title: Replace cold PR detail spinner with shared loading skeletons
kind: feature
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: pulls_navigation
labels: []
dependencies: []
parent_id: is-01m6hx4w87z6r8ndnbt57avr53
hold: null
hold_until: null
created_at: 2026-11-03T23:59:16.995Z
updated_at: 2026-11-04T17:14:29.996Z
started_at: 2026-11-03T23:59:29.644Z
closed_at: 2026-11-04T17:14:29.996Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Use existing gray pulsing skeleton tokens and loading delay for genuinely cold/pending PR detail. Keep cached PR data readable during refresh; no skeleton on absent/setup/error outcomes. Preserve accessible loading name, reduced-motion treatment and reading-column geometry. Review actual loading states, add targeted session coverage and regenerate truthful affected goldens.

## Notes

Writer handoff above a78ad4c5. Cold/pending PR detail uses nested delayed wrapper/shared neutral recent-loading pulse; cached refresh retains content. PR-only initial shell and no-record Files skeleton use reading column; ordinary preview unchanged. Mounted cold/pending/cache/identity tests and focused shell assertion pass. Source frozen; coordinator owns final formatting/commit/full gate; exact installed-wheel narrow/wide/reduced-motion screenshots pending. See stack-ui-a78ad4c5/frontend-final-handoff.json in durable agent evidence.
