---
type: is
id: is-01kytq1nfrxs83px1dvrtmsza3
title: Unify typography on a semantic type scale; fix KPress px/rem embedding seam
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-07-30T23:51:38.740Z
updated_at: 2026-07-30T23:51:43.576Z
closed_at: 2026-07-30T23:51:43.575Z
close_reason: "Implemented and verified: make verify passes (741 tests), two-root browser check confirms root-independence"
---
Consolidate all app font sizes onto documented type-scale tokens (chrome: 14/13/12/10px; document: 17px + derived mono 0.9x and small 0.85x); unify small-caps labels (tabs, DIAGNOSTICS, FRONTMATTER, table headers, TOC CONTENTS title) on one size/weight/color tier; fix TOC entry inset and hanging indent; reduce tab vertical padding. Root cause of the recurring inconsistencies: KPress sizes in rem (browser-root-dependent) while the app pins px — the KPress bridge now remaps every KPress size token and restates its rem literals (headings, bullets, widget labels) in em, verified identical at 16px and 13px browser roots. Documented in docs/design-system.md (Type Scale + px/rem Unit Boundary).
