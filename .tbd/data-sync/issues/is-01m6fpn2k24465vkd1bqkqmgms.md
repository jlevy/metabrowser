---
type: is
id: is-01m6fpn2k24465vkd1bqkqmgms
title: "PR #281 D4: a wrapped path's trailing badge drops under the button form of a text action"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fpn0yb9yn4kakx1qp787e4
hold: null
hold_until: null
created_at: 2026-11-03T03:18:42.017Z
updated_at: 2026-11-03T04:10:44.868Z
started_at: 2026-11-03T03:50:29.946Z
closed_at: 2026-11-03T04:10:44.867Z
close_reason: "Fixed in 314fcd64: .github-pull-file is inline-block in every form, so link and button lay out alike. Measured in headless Chrome over production CSS at 685 px: link head 45 px vs button 63 px before; both 63 px after; one-line head unchanged at 25.5 px. Pinned in test_design_vocabulary. CI green."
resolution: null
duplicate_of: null
---
Low. pull-page.js fileLink button form vs link form; docs/design-system.md:406-416. Fix: wrapping flex row for the card head, or record the difference. Review: https://github.com/jlevy/metabrowser/pull/281#pullrequestreview-5746822976 (PR #281, head 7bef1356).
