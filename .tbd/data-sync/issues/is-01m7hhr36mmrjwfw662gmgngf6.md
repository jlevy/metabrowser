---
type: is
id: is-01m7hhr36mmrjwfw662gmgngf6
title: "Release 0.13: previous-release performance comparison (v0.12.0 vs exact candidate)"
kind: task
status: in_progress
priority: 1
version: 11
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45109522719
    at: 2026-11-23T04:05:53.983Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45110293239
    at: 2026-11-23T04:26:20.765Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45112075401
    at: 2026-11-23T05:11:14.326Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45113677625
    at: 2026-11-23T05:11:14.331Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45113917455
    at: 2026-11-23T05:11:14.331Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45116045122
    at: 2026-11-23T05:11:14.331Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45117924502
    at: 2026-11-23T05:29:05.445Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
child_order_hints:
  - is-01m83bbgeajzxhr6xkpabzgs0c
hold: null
hold_until: null
created_at: 2026-11-16T06:47:08.755Z
updated_at: 2026-11-23T05:29:05.458Z
started_at: 2026-11-23T03:13:34.430Z
---

## Notes

2026-11-17 coordinator: renumbered from exp-088 to exp-099, which has since been used for an earlier candidate. Main contains exp-099 through exp-101. Reserve the next unused number after checking the parallel performance plan when the release candidate is pinned.

Use the installed-wheel control and candidate on one unchanged project-10 corpus with five interleaved runs for both backend and visible headed Chromium, as prescribed by the release checklist. The prior comparable run (exp-034) used a quiet Linux cloud container with 1-minute load below 1.1. On 2026-11-22 the shared Mac's 1-minute load exceeded 200 and the prior Linux runner was unavailable. Exclude timings under those conditions.

Two hosted exact-wheel runs compared v0.12.0 (87b8ec812) and 0.13.0 draft runtime (29f9f8c3) on unchanged public project-10 corpora. Each returned five complete backend pairs with zero ordered-row differences and the same nine explained tally differences (registry schema/revision/fingerprint and docs-before-code presentation). First-row medians were 9 ms for both sides, then 10 ms for both sides. KPress 0.3.5 to 0.3.9 was the only non-Metabrowser runtime dependency delta. The stock Google Chrome attempt produced a visible control profile with 34.1% input coverage and was refused by the unmodified minimum-80% gate. The stock Chromium retry produced no profile file in all ten control/candidate attempts. No browser row reached the ledger or cleared the browser gate. A guarded early-input diagnostic for the known-working browser is staged for review.

Matched HTTP diagnosis: original TCP-ready series admitted all 10 captures but candidate navigations began before the app could answer. All 5 missed 350 ms, 697–765 vs 131–242 ms. With the same lightweight HTTP readiness boundary, all five exact 29f9f8c3 candidates passed every hard gate (211–230 vs 112–301 ms), but four paired timings miss the 1.3× rough-cut tolerance. Broader font revision 78e3cdb3 replicated the relative miss in four admitted pairs. Control coverage and candidate cleanup each refused one attempt. The stock comparator still refuses the different locked KPress environments. Exact combined narrowed font + TCP candidate ed7e1f10 is now running (45116045122). Evidence for initial and matched regimes is committed locally as 6adc0dfd9; all raw artifacts retained.
