---
type: is
id: is-01m0gxwpvw71h9h63ezt6pak5w
title: Audit every themed token against the hue-invariance rule
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-21T01:10:15.675Z
updated_at: 2026-08-21T01:33:30.718Z
closed_at: 2026-08-21T01:33:30.717Z
close_reason: "Landed: 35 chromatic tokens aligned to their light hue, near-neutrals exempted as imperceptible, and the rule enforced exactly by test_design_vocabulary; contrast suites converted to oklch math and still pass."
---
design-system.md now states the theming rule (a token defined in both themes keeps its hue; lightness and chroma are tuned per background) and test_design_vocabulary.py enforces it for tokens already in oklch — 16 pairs today. Two follow-ups: (1) audit tokens defined in only one theme, since a literal tuned for light is unreadable on dark (this is how --git-ref-local broke); (2) once the oklch migration lands (mb-r22h), the check covers the whole palette, so re-run it and fix or document every violation. Keep the lane-color set as the documented exception.
