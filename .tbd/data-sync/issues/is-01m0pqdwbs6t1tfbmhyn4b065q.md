---
type: is
id: is-01m0pqdwbs6t1tfbmhyn4b065q
title: exp-006 phrases a phase measurement as a first-paint claim
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T07:12:44.920Z
updated_at: 2026-08-30T09:08:46.787Z
---
exp-006's headline is phrased as a first-paint claim and measures a phase. Both halves are defensible; together they mislead.

WHAT IT SAYS: "twenty seconds of dead time before the first row, gone", above a table reading 21.37s -> 2.18s on real tree A and 13.36s -> 0.81s on the reproducible corpus.

WHAT THE TABLE MEASURES: the gitignore pre-walk, timed as a phase. Confirmed by timing build_gitignore_check_for directly on the corpus exp-006 names -- the candidate comes in at 0.879s against the 0.81s reported, so the table is reproducible on its own terms.

WHAT A READER SEES INSTEAD, measured over HTTP on that same corpus: skeleton rows arrive at 1.3s on BOTH builds. The pre-walk cost lands in total index time, not before the first row. Neither build delivers a row carrying data early; both deliver placeholders first, and data arrives at settle.

SO THE NUMBER IS RIGHT AND THE SENTENCE IS NOT. A phase that runs before indexing is not the same thing as the delay a reader experiences before seeing something, because the server answers with skeleton rows while it works. Anyone reading the claim as first-paint latency -- as this validation initially did, and spent a round of measurement on -- will fail to reproduce it and be right not to.

WHAT TO DO: reword the claim to say what was measured (the pre-walk phase, and the total index time it sits inside), and if a first-paint number is wanted, measure that separately and say which it is. The win is real and large either way; this is about which win is being claimed.

RELATED, from the same validation and worth folding in: the reproducible corpus figure did not reproduce for the BASELINE either -- 2.53s measured against 13.36s reported -- most likely because exp-006 cleared the page cache between runs and this run could not. If that is right, the exp-006 table should say the cache state it requires, since the baseline's cost is a metadata walk over ~222k directories and a warm cache erases most of it. See mb-j7xx.

## Notes

FIXED. exp-006's headline now reads "twenty seconds of the pre-walk phase, gone" rather than "dead time before the first row", and the section carries what the numbers do and do not say.

WHY THE OLD WORDING WAS WRONG RATHER THAN LOOSE. Those figures time `load_gitignore` itself. Measuring the same corpus over HTTP found skeleton rows arriving at about 1.3s on BOTH builds, because the server answers with placeholder rows while it works. So the cost sits inside total index time rather than in front of the first row, and a reader who took the sentence at face value would go looking for a first-paint improvement that is not there -- which is exactly what happened during the 0.6.1 validation and cost a round of measurement.

ALSO RECORDED, because it is the other half of why the figure would not reproduce: the numbers need a cold cache. Re-measuring the reproducible corpus later read 2.53s and then 1.33s for the control as the page cache warmed, against 13.36s in the table, while the candidate repeated itself at 0.879s and 0.897s. The control walks the whole tree and the candidate prunes it, so only one of them is cache-sensitive -- which is the evidence for the reading rather than an excuse for it. The section now says the runs cleared the cache and that a host where it cannot be dropped will understate the control.

The measurement stands and the verdict is unchanged. Only the claim it was described as making has been corrected.
