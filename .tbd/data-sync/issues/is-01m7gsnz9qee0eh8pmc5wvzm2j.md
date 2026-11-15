---
type: is
id: is-01m7gsnz9qee0eh8pmc5wvzm2j
title: "Filter triggers: an active trigger reads 4.15:1 in light, below 4.5:1"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T23:46:33.398Z
updated_at: 2026-11-15T23:46:33.398Z
---
Found by the mb-xlla (design-system consistency code fixes) agent, 2026-11-15, measured in headless Chrome at claude/ds-consistency-code (cfe2d2ed9).

An active chip-menu trigger (`data-active`, drawn `--link` on `--highlight-bg`, styles.css:3383-3388) reads 4.15:1 at rest in the light theme and 5.98:1 in dark. Light is below WCAG AA's 4.5:1 for normal text. This applies to every active filter trigger (Group by, Modified within, File type, Minimum file size) and predates this round. mb-xlla stopped the Group by trigger breathing, which had dropped it to 3.03:1.

Done when an active trigger meets 4.5:1 in both themes, by token, for example a darker active ink or a lighter active ground, stated in the design system's Filter Controls. Measured in Chrome and pinned in the contrast test (`test_refreshing_text_breathes_on_the_compositor_and_keeps_its_contrast` or a sibling).
