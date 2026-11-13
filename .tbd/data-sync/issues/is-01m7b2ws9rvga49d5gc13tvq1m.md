---
type: is
id: is-01m7b2ws9rvga49d5gc13tvq1m
title: "Branch chips: slightly smaller than the surrounding text, everywhere (one ratio, not one size)"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T18:32:07.223Z
updated_at: 2026-11-13T19:23:14.692Z
closed_at: 2026-11-13T19:23:14.691Z
close_reason: "Merged in #401: every branch chip is 0.9 of the text around it (--git-ref-font-scale), measured in each context; the size check covers plugin styles."
resolution: null
duplicate_of: null
---
The user (2026-11-13): "the chips for branches shoudl use slightly smaller font everywhere as appropriate, relative ot the surrounding text size."

Today `.git-ref` has one fixed size, `--ui-small-font-size` (12px), everywhere: history rows, the commit summary and tooltip, the PR header, Pulls rows, the ref selector, and `.merge-refs`. #393 set that "one size" rule on purpose, and `docs/design-system.md` (Branch Chips) records it.

The user's newer direction replaces it: one ratio, not one size. Every chip is slightly smaller than the text around it.

Done when:
- the chip's font size is relative to its context (a token for the ratio);
- the line box, padding, max-width, HEAD ring, tag notch, and the `.merge-refs` minimum scale with it, or are measured to still fit;
- a legibility floor is set from measurement, if one is needed;
- Branch Chips in the design system states the ratio rule;
- a test pins the ratio in every context.

## Notes

2026-11-13: PR #401 (claude/ui-ref-chip-ratio, head 92961152). --git-ref-font-scale 0.9 in em; measured in Chrome: history 13->11.7px, summary, tooltip, and PR header 14->12.6px, Pulls and the ref selector 12->10.8px. Review A running.
