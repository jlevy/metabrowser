---
type: is
id: is-01m774rsh9sd7x3aygqmew3zax
title: "Layer 4: reveal presentation and strip layer"
kind: task
status: closed
priority: 2
version: 7
spec_path: docs/project/specs/done/plan-2026-11-11-shift-key-reveal-and-keymap.md
delegate: claude-code@spud10
labels:
  - layer-4
dependencies:
  - type: blocks
    target: is-01m774rv75dzyrdjgrxs9erjth
parent_id: is-01m76jgfxbadse383jypkzwpm9
hold: null
hold_until: null
created_at: 2026-11-12T05:47:55.814Z
updated_at: 2026-11-13T16:45:48.668Z
started_at: 2026-11-12T20:40:23.063Z
closed_at: 2026-11-12T21:55:02.577Z
close_reason: "Done in 118786d5, 3bb74934, 8f78aed0: --key-reveal-bg (var(--row-flash-bg)), --kbd-badge-bg (the yellow at 0.6 alpha), --kbd-badge-border, and --kbd-badge-color in both themes at hue 98.1; .kbd-badge after the base .kbd rule, paint only, absolute and pointer-events none; inline-end and beside placement; :where(.kbd-badge-host) and :where([data-kbd-badge-anchor]) containing blocks; [data-key-reveal] .icon-btn-reveal[aria-keyshortcuts] override; .nav-shortcut-reveal out of flow against the host's bottom edge with --text; fade in, none under reduced motion, never printed. Contrast light strip 15.46:1, badge 15.10:1; dark strip 4.76:1, badge 6.55:1, recorded beside the tokens. Tests: tests/test_design_vocabulary.py (test_key_reveal_tokens_are_the_row_flash_yellow_in_both_themes, test_key_reveal_text_meets_contrast_in_both_themes, test_key_badges_are_positioned_paint_over_layer_three_markup, test_hover_revealed_targets_show_while_keys_are_revealed, test_key_reveal_fades_in_hides_at_once_and_respects_reduced_motion, test_key_reveal_never_prints, test_revealed_strip_overlays_the_panel_without_reflowing_it) and tests/test_chrome_typography.py test_badge_keycap_modifies_the_base_rule_after_it; make test 5398 passed, 412 goldens. Still provisional, for a person: REVEAL_HOLD_MS and REVEAL_POINTER_SLOP_PX (QA runbook 3.4 check 13); REVEAL_STRIP_MAX_ITEMS stays 8 with its Chrome rows recorded, since no cap fits the bottom-quarter rule at 200% zoom."
resolution: null
duplicate_of: null
---
Design > Reveal Presentation and Shortcut Strip in Reveal Mode. Badge and reveal tokens in both themes at --row-flash-bg hue; .kbd-badge after the base .kbd rule; inline-end and beside placement with header anchors; reveal-on-hover override; strip reveal layer over a fixed-height host with --text; measured contrast, REVEAL_HOLD_MS, REVEAL_POINTER_SLOP_PX, and strip item count; reduced motion; print; paint-exempt row shell.key-badge-paint.
