---
type: is
id: is-01m7g5w0nr4cbfm4xtmtqzztrh
title: "PR page: the stack chip leads the author's row, under the title"
kind: task
status: in_progress
priority: 2
version: 6
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T18:00:19.895Z
updated_at: 2026-11-17T05:58:39.297Z
started_at: 2026-11-15T18:00:53.720Z
---
The user's request (2026-11-15), verbatim:

"also on the main PR view page let's make a couple changs

the button with the stack icon and number should go directliy below the PR title, to the left of the author."

Today the stack chip sits in a slot at the end of the labels row (static header layout in builtin_plugins/github/pull-page.js `mountPullPage` and `paintHeader`; docs/design-system.md, "The Pull Request Page"), chosen so a stack arriving after first paint moves nothing.

Done when the stack chip leads the row directly under the title, left of the author ("[Stack #N] [avatar] jlevy wants to merge ..."), and the header still moves nothing when the stack's answer arrives after the first paint: no horizontal shift of the author line and no vertical shift of the rows below. Measured in Chrome (and in WebKit if the driver path is quick) with the stack arriving late, early, and never. The design system and the header Chrome checks say so.

## Notes

2026-11-15: no implementation yet. Every approach that puts the chip first in the author's row trades a cost the owner should choose, so these options are reported to the coordinator instead.

Measured in headless Chrome 152 on the production header (recorded PR 7, author with an avatar), at 980, 560 and 360 px, with the chip built by createStackMenu (Layers glyph plus position):
- Chip widths: "1/2" 54.75 px, "5/23" 61.08 px, "12/23" 67.42 px; two memberships ("4/4" and "2/2") 109.5 px.
- A. Chip first, nothing reserved. Early (index held at first paint) and never: 0 shift. Late: the author shifts right by the chip width plus the row's 8 px gap: 62.75 / 69.08 / 75.42 px, and 125.5 px for two memberships. At 360 px two chips also cut the sentence by 48.14 px. Rows below moved 1 px (the details element is 1 px taller than the row's strut), which CSS can fix.
- B. Slot reserved at the width of a "99/99" chip, in every header. Late: 0 shift for one chip. Two memberships (109.5 px) overflow the 99.42 px slot. Never in a stack: the author starts 99.42 px from the header's edge instead of 24 px, a 75.42 px empty gap on every PR not in a stack. Same 1 px row move, also fixable.
- C. Hold the header's first paint for the stacks answer within an existing bound (DESCRIPTION_HOLD_MS, 200 ms). 0 shift when the index is already held (the controller is shared module-wide, so the Pulls tab or an earlier PR page in the document has it) or when the cache-only GET answers within the bound. Otherwise it shifts as in A: a first refresh with no snapshot yet, a stack created while the page is open, or a GET slower than the bound. GET latency was not measured.
- D. Chip first when membership is known at first paint; a chip that arrives later takes today's slot at the end of the labels row, and moves to the front on the next mount. 0 shift and no gap, but the chip's place depends on timing. Today's behavior covers the late half.

Decision, the user (2026-11-15), verbatim: "on the stack then let's find a way to avoid the problem altogether, e.g. put it right aligned below the right aligned PR number, on same line as author". So the stack chip sits at the right end of the author's row, aligned under the title's right-aligned PR number. A chip that arrives late lands in the row's empty end and moves nothing: no shift of the author, no reserved gap. This supersedes options A to D.
2026-11-15, implemented as decided (chip at the right end of the author's row): commit 5efb99b78, pushed --no-verify. A late chip lands in the row's empty end at the header's content edge. In headless Chrome 152 at 980 to 320 px, one stack (54.75 px) and two (113.5 px), no part's start, row or tab bar moved; the chip keeps 8 px from the sentence. Where room runs out, the sentence is cut at its end: 34.88 px at 560 px (long names, two stacks), 38.04 px at 360 px (short name, two stacks). The details element is not taller there, so no fix was needed. Title finding: the title grid (auto | minmax(0, max-content) | auto) does not right-align the number. A title that fills its lines ends with the number at the content edge; with a short title the two auto tracks split the free space, so at 980 px the text sits centered (361 to 608 px) after a lone icon and '#7' follows it at 616 px. The chip aligns to the content edge.
