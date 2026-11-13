---
type: is
id: is-01m774r7k4mqvs813sjppzvceh
title: "PR page: join the click to the peek, same-frame list collapse, hold Changes first paint"
kind: task
status: closed
priority: 2
version: 13
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-12T05:47:37.443Z
updated_at: 2026-11-13T16:39:08.992Z
started_at: 2026-11-12T06:11:46.651Z
closed_at: 2026-11-13T16:39:08.991Z
close_reason: "Landed in #369 (merge 597a7c70). exp-065 (H92) accepted on all three parts: duplicate reads of the selected record 6 -> 0, the no-input Pulls panel shift 0.05 -> 0 (pilot tree probe), and Changes body shift after painted ready 1.0851 -> 0, n=3 pairs (6 excluded for load before results were read). Guard cost stated and accounted for by the measured hold: Changes painted ready 33-64 ms later in every pair (changesHold median 58 ms). Reviews A-F done."
resolution: null
duplicate_of: null
---
One read of the selected PR per click (join the mousedown peek); collapse the old and expand the new Pulls row in one frame; reserve a selected row's file-tree height at the click or open it only when rows are known; hold Changes first paint for rendered diffs already in flight or reserve their heights. Measured as selected-record reads per click and no-input shift (largest today 0.146 from the late file tree).

## Notes

PR #369. Round-1 reviews at 9484c273: A senior (5876269909), B performance (5876272262); 0 Blocker, 0 High, 11 Medium, 10 Low. Addressed at 593beceb (337b6526 tree offers and focus; d717bb1a reads aborted; cc79ca24 superseded commit rows; f3707613 holds cover comments and reviews, Changes lands first, ages refresh; d62da2ce parity rows; bb06bf56; 593beceb). Dispositions 6827909624/6827910292; coordinator note 6827956671; deferrals mb-5lfu (A15), mb-fejb note (B4), mb-nebu (B6). Measured holds (Chrome 152, n=5-24): firstPaintHold median 19 ms p90 68; changesHold 39/90; openingHold 23/42; none hit bound. Follow-up review C in progress. Official exp-065 and exp-080 on harness v4 after review C, behind the series lock.


Follow-up review C (round 2, 593beceb, 5877695054): approve; 2 Medium (C1 hold picks the first screen from the replaced page's scroll; C2 slow landing shows blocks, then empty, then content), 5 Low. Fixing before the official rounds.


Review C addressed at 3afd3131 (4ff1cf9f C1 first screen from the new page's own top, re-measured as texts land; C2 visible blocks stay until content; C5; 3afd3131 C3, C4, C6, C7); dispositions 6829270629. Holds re-measured from scrolled conversations (n=10-14): firstPaintHold median 34 ms, changesHold 39, openingHold 31; none hit bound. Follow-up review D (round 3, narrow) in progress. exp-065 and exp-080 queued behind the series lock at 3afd3131.
Follow-up review D (round 3, 3afd3131, 5878410290): approve; 1 Medium (D1 kept loading blocks drop by the header's growth when the record arrives: CLS 0.039 on every slow cold landing), 3 Low. Fixing D1 before the rounds; coordinator verifies D1 with the reviewer's harness instead of another full round.
Review D addressed at 5a56f0a8 (cf117163 header held with the body; 5a56f0a8 D4); dispositions 6830212104. Coordinator verified D1 with review D's harness (comment 6830266303): six landing stories, layout shift 0.039 in five at 3afd3131, none at 5a56f0a8; 45 ms landing shows no blocks. Review rounds for #369 complete. exp-065 and exp-080 at 5a56f0a8 behind the series lock.
