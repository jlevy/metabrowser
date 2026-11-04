---
type: is
id: is-01m6j7mjcjmn42yqwcqvwbwkwq
title: Use consistent GitHub destination icons for external links
kind: feature
status: closed
priority: 1
version: 8
spec_path: docs/design-system.md
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
child_order_hints:
  - is-01m6ja4vx6617n2t5ks5k0pcn7
  - is-01m6jak66bp875jeya2praycwk
created_at: 2026-11-04T02:54:00.081Z
updated_at: 2026-11-04T17:14:30.851Z
closed_at: 2026-11-04T17:14:30.851Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Owner requests a shared external GitHub link icon convention: generic GitHub destinations use the GitHub icon, issue and PR destinations use appropriate entity/state icons when state is known. Audit app-owned links and Markdown/shared link enhancement, retain safe external-link behavior and accessible names, avoid per-link API calls or invented states. Implement as a focused additive stacked change and verify with concise production-module sessions plus visual checks.

## Notes

Final icon layer40925ab2 over owning design98db8ff3, normal forward merges only. Independent source/test/docs review clean and341production entries identical reviewedbdf; inherited golden-only repair reviewed separately. Existing4096 Markdown bound/localization/sanitization preserved, no provider or remoteSVGcalls. Fresh artifact acceptance and aggregate full gate in progress; final publication six followups, native286eleven members, twentyPRs overall. No merges authorized.
