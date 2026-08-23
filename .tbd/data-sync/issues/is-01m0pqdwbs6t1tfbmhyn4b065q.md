---
type: is
id: is-01m0pqdwbs6t1tfbmhyn4b065q
title: exp-006 phrases a phase measurement as a first-paint claim
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T07:12:44.920Z
updated_at: 2026-08-23T07:12:44.920Z
---
exp-006's headline is phrased as a first-paint claim and measures a phase. Both halves are defensible; together they mislead.

WHAT IT SAYS: "twenty seconds of dead time before the first row, gone", above a table reading 21.37s -> 2.18s on real tree A and 13.36s -> 0.81s on the reproducible corpus.

WHAT THE TABLE MEASURES: the gitignore pre-walk, timed as a phase. Confirmed by timing build_gitignore_check_for directly on the corpus exp-006 names -- the candidate comes in at 0.879s against the 0.81s reported, so the table is reproducible on its own terms.

WHAT A READER SEES INSTEAD, measured over HTTP on that same corpus: skeleton rows arrive at 1.3s on BOTH builds. The pre-walk cost lands in total index time, not before the first row. Neither build delivers a row carrying data early; both deliver placeholders first, and data arrives at settle.

SO THE NUMBER IS RIGHT AND THE SENTENCE IS NOT. A phase that runs before indexing is not the same thing as the delay a reader experiences before seeing something, because the server answers with skeleton rows while it works. Anyone reading the claim as first-paint latency -- as this validation initially did, and spent a round of measurement on -- will fail to reproduce it and be right not to.

WHAT TO DO: reword the claim to say what was measured (the pre-walk phase, and the total index time it sits inside), and if a first-paint number is wanted, measure that separately and say which it is. The win is real and large either way; this is about which win is being claimed.

RELATED, from the same validation and worth folding in: the reproducible corpus figure did not reproduce for the BASELINE either -- 2.53s measured against 13.36s reported -- most likely because exp-006 cleared the page cache between runs and this run could not. If that is right, the exp-006 table should say the cache state it requires, since the baseline's cost is a metadata walk over ~222k directories and a warm cache erases most of it. See mb-j7xx.
