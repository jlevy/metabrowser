---
type: is
id: is-01m7b1shq59yawwhptfdgba5xg
title: Commits digit focuses the old row after the newest-commit landing
kind: bug
status: in_progress
priority: 2
version: 7
spec_path: docs/project/specs/done/plan-2026-11-11-shift-key-reveal-and-keymap.md
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m76jgfxbadse383jypkzwpm9
child_order_hints:
  - is-01m7b507nf5nftb8myezzyf6qr
  - is-01m7b508gkdp6rv2txhpwy32kx
  - is-01m7b5099db4w163yz83yhz98s
  - is-01m7b50a2f1mza66bdtegar5yn
  - is-01m7b50avjsgsh3es0xc03855r
hold: null
hold_until: null
created_at: 2026-11-13T18:12:52.580Z
updated_at: 2026-11-13T19:09:00.657Z
started_at: 2026-11-13T18:13:07.673Z
---
After #395 (Commits selects the newest commit), the `2` key runs openMainTab, which starts landOnNewestCommit, and then synchronously calls focusCommitRow. That focuses the roving anchor still mounted, the previously selected older commit, while the landing later selects the newest. Focus and selection split: Down or J then moves from the old row. design-system.md also contradicts itself (digit moves focus to the roving row vs. focus stays on the tab). Fix: the digit lands focus on the newest row; reconcile the docs; add a shortcut variant to the switching-to-Commits session. Also fix the done spec's stale C/G/H sentence after #369's held first paint, and the CHANGELOG Unreleased 'Rendered by default' entry that #394 and #397 contradict.
