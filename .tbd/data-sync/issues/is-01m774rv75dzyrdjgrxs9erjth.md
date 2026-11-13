---
type: is
id: is-01m774rv75dzyrdjgrxs9erjth
title: "Layer 4: browser QA, contrast, and paint-exempt row"
kind: task
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/done/plan-2026-11-11-shift-key-reveal-and-keymap.md
delegate: claude-code@spud10
labels:
  - layer-4
dependencies: []
parent_id: is-01m76jgfxbadse383jypkzwpm9
hold: null
hold_until: null
created_at: 2026-11-12T05:47:57.521Z
updated_at: 2026-11-13T16:45:49.424Z
started_at: 2026-11-12T21:04:55.003Z
closed_at: 2026-11-12T21:55:02.965Z
close_reason: "Done in c9e6818d: shell.key-badge-paint paint-exempt row (devtools.check_parity passes, citing tests/test_design_vocabulary.py and tests/test_chrome_typography.py); QA runbook 3.4 check 14 (both themes, 200% zoom, narrowest pane, narrow window, reduced motion) and Part 4's Safari/Firefox repeat now naming checks 13 and 14; measured contrast recorded beside the tokens and recomputed by test_key_reveal_text_meets_contrast_in_both_themes; design-system Badge Targets and the Shift Reveal; CHANGELOG under Unreleased. Headless Chrome 152 ran check 14 on a mirror pin's Markdown file, a folder, and a commit: no clipped badge except on a tab cut off by the window, no reflow, reduced motion and print honored, reveal to frame about 4 ms small and 16-18 ms on a 15,000-element page. Left for a person: check 14 in real Chrome, Safari, and Firefox."
resolution: null
duplicate_of: null
---
Spec Rollout layer 4 docs. QA runbook reveal check in Chrome, Safari, Firefox (both themes, 200% zoom, minimum nav width, narrow viewport); measured contrast ratios recorded beside tokens; parity row shell.key-badge-paint; CHANGELOG entry.
