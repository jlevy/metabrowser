---
type: is
id: is-01m88ndnds6mtpa7f6ks2hs36g
title: "PR page stack menu: show each member's PR number"
kind: feature
status: in_progress
priority: 1
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/827
    at: 2026-11-25T09:03:34.748Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-25T06:13:53.201Z
updated_at: 2026-11-25T11:50:55.205Z
started_at: 2026-11-25T06:14:29.104Z
---
Asked by the user after #817 merged: the stack menu opened from the PR page's stack chip shows each member as [state icon] bold place · title, with the PR number said to screen readers but not shown. Show the PR number too, in the same face the Pulls tab's rows draw it (#455). Done when each member line shows its number, muted and never cut (the title is cut short before it), read once by a screen reader (the hidden copy removed), and pinned in the stack-groups session, its golden, and a Chrome check.

## Notes

Decision (2026-11-25, PR #827): the done criterion said both "muted" and "in the same face the Pulls tab's rows draw it"; those contradict, since a Pulls row's number is in text ink at the number's weight. Kept the Pulls-row face: the member's number is in the text's ink at --pull-number-weight (.github-pull-stack-member-number), not muted. Later, mb-pw8t put the member's place before the number at the line's end, "1/6 · #455", the Pulls row's order.
