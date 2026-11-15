---
type: is
id: is-01m7d6qy7eb6m07raw2ct53hpg
title: "H108 (exp-088): what H114 and H112 (d) leave of preparing Changes' first screen before the click"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-14T14:17:51.597Z
updated_at: 2026-11-15T07:01:11.282Z
---
exp-079 accepted H92 (c) as the campaign's costliest trade: at final main Changes is ready at 79 to 102 ms against 43 to 45 ms in the control, the price of holding first paint until the first screen's diffs are rendered (CHANGES_FIRST_SCREEN_MS = 200). H106's Conversation hold costs pull request clicks similarly (44 to 112 ms against 28 to 62 ms). Register a hypothesis: preparing the first screen's diffs and description on selection or pointer intent makes the hold resolve at once, keeping zero movement and winning back the time. Guards: wasted prepare requests, the hold-span probe, and exp-079's PR transitions.

## Notes

2026-11-14: re-scoped by the architecture review. H114 (mb-3zvb) takes H108's description half (the pull route carries the first screen's rendered texts), and H112 (d) (mb-wki1) its Changes half (Changes mounted at idle). Keep this bead for whatever H108 still covers after both are measured; otherwise close it as superseded.
