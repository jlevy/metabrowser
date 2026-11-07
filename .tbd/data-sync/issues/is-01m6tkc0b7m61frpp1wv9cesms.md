---
type: is
id: is-01m6tkc0b7m61frpp1wv9cesms
title: Align PR author and opened-age metadata on one baseline
kind: bug
status: in_progress
priority: 2
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T08:52:57.820Z
updated_at: 2026-11-07T08:56:38.991Z
started_at: 2026-11-07T08:56:38.990Z
---
User reports the PR header line jlevy opened 2d ago has inconsistent font sizes and baselines: the larger username does not sit on the same text baseline as opened/age. Use one metadata font size and line height across author, opened and age, with username emphasis by weight/color. Align text baselines while keeping the avatar optically centered and branch chips on their appropriate smaller scale. Scope styling to the shared PR identity component so other condensed age/nav text stays correct; verify real rendered browser geometry, wrap/narrow behavior, and normal font modes. Deliver as a focused stacked follow-up, document the design, and update the bead after review/verification.
