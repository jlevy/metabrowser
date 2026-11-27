---
title: "The Cached Pull Request Page's Regression Is #369's First-Paint Hold"
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-099
  title: "The Cached Pull Request Page's Regression Is #369's First-Paint Hold"
  date: "2026-11-17"
  hypotheses:
    - H119
  subject:
    corpus: >-
      A clean linked worktree of this repository at 4eb299fd1, served as a folder in
      checkout mode against the live jlevy/metabrowser repository on GitHub: pull requests
      #470 (36 files), #487 (35 files, four texts on its first screen), and #514 (store
      preparation only), and the open Pulls list.
    corpus_files: 1875
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0 arm64; one-minute load average 5 to 13 from other sessions
    browser: Headless Chrome 152 over the DevTools Protocol, a fresh profile per server, visibilityState visible
    viewport: 1400x813
    cold: true
  method:
    runs_per_condition: 3
    interleaved: true
    control: metab 0.12.0 (87b8ec812), installed from a wheel built by pr-view-wheel.sh
    candidate: >-
      metab 0.12.1.dev1621+c6aa0208 (main at #513, c6aa02085), installed from a wheel built
      by pr-view-wheel.sh into the same environment
    protocol:
      path: exp-099-protocol.txt
      sha256: 45de16165348e98e47268eb1215be3844c3beadcdc58bd77d036ed23c7d71471
    record: >-
      exp-099-pairs-v0120-main.jsonl (the judged series), with the bisect and context
      series exp-099-pairs-369.jsonl, exp-099-pairs-v0120-n12.jsonl,
      exp-099-pairs-369-main.jsonl, exp-099-pairs-pulls-pf.jsonl, and the browserless
      exp-099-first-routes.jsonl; read each with pr-view-stats.mjs
  results:
    - metric: v0120_main.pr-warm.title_ms
      control_median: 683
      candidate_median: 961
      control_range: [640, 694]
      candidate_range: [910, 1014]
      change_pct: 40.7
      overlapping: false
    - metric: v0120_main.pr-warm.description_final_ms
      control_median: 803
      candidate_median: 961
      control_range: [760, 813]
      candidate_range: [910, 1014]
      change_pct: 19.7
      overlapping: false
    - metric: v0120_main.pr-warm.complete_ms
      control_median: 803
      candidate_median: 998
      control_range: [760, 813]
      candidate_range: [969, 1086]
      change_pct: 24.3
      overlapping: false
    - metric: v0120_main.pr-warm-reload.title_ms
      control_median: 102
      candidate_median: 126
      control_range: [100, 103]
      candidate_range: [124, 181]
      change_pct: 23.5
      overlapping: false
    - metric: v0120_main.pr-warm-reload.description_final_ms
      control_median: 148
      candidate_median: 126
      control_range: [141, 153]
      candidate_range: [124, 181]
      change_pct: -14.9
      overlapping: true
    - metric: v0120_main.pr-warm.first_pull_get_ms
      control_median: 425
      candidate_median: 513
      control_range: [420, 448]
      candidate_range: [512, 555]
      change_pct: 20.7
      overlapping: false
    - metric: v0120_main.pr-fresh.title_ms
      control_median: 1602
      candidate_median: 1708
      control_range: [1469, 1646]
      candidate_range: [1508, 1742]
      change_pct: 6.6
      overlapping: true
    - metric: v0120_main.pr-fresh.description_final_ms
      control_median: 2611
      candidate_median: 2633
      control_range: [2472, 2690]
      candidate_range: [2489, 2814]
      change_pct: 0.8
      overlapping: true
    - metric: v0120_main.pr-store.title_ms
      control_median: 1627
      candidate_median: 1798
      control_range: [1581, 1744]
      candidate_range: [1608, 1804]
      change_pct: 10.5
      overlapping: true
    - metric: v0120_main.pr-store.description_final_ms
      control_median: 3276
      candidate_median: 3333
      control_range: [3102, 3395]
      candidate_range: [3306, 3917]
      change_pct: 1.7
      overlapping: true
    - metric: v0120_main.pulls-cold.first_row_ms
      control_median: 2491
      candidate_median: 2499
      control_range: [1488, 2514]
      candidate_range: [1507, 2535]
      change_pct: 0.3
      overlapping: true
    - metric: v0120_main.pulls-warm.first_row_ms
      control_median: 755
      candidate_median: 780
      control_range: [583, 876]
      candidate_range: [738, 809]
      change_pct: 3.3
      overlapping: true
    - metric: v0120_main.pulls-warm-reload.first_row_ms
      control_median: 103
      candidate_median: 83
      control_range: [101, 120]
      candidate_range: [79, 91]
      change_pct: -19.4
      overlapping: false
    - metric: before_369_vs_369.pr-warm-reload.title_ms
      control_median: 112
      candidate_median: 204
      control_range: [110, 114]
      candidate_range: [186, 231]
      change_pct: 82.1
      overlapping: false
    - metric: before_369_vs_369.pr-warm-reload.description_final_ms
      control_median: 139
      candidate_median: 204
      control_range: [128, 143]
      candidate_range: [186, 231]
      change_pct: 46.8
      overlapping: false
    - metric: before_369_vs_369.pr-warm.title_ms
      control_median: 739
      candidate_median: 926
      control_range: [723, 809]
      candidate_range: [855, 935]
      change_pct: 25.3
      overlapping: false
    - metric: v0120_vs_nov12.pr-warm.title_ms
      control_median: 637
      candidate_median: 647
      control_range: [580, 750]
      candidate_range: [617, 696]
      change_pct: 1.6
      overlapping: true
    - metric: 369_vs_main.pr-warm-reload.title_ms
      control_median: 231
      candidate_median: 123
      control_range: [229, 241]
      candidate_range: [109, 149]
      change_pct: -46.8
      overlapping: false
  complexity:
    lines_changed: 0
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      A measurement round: no product code changes. It adds the pr-view benchmark
      (pr-view.mjs, pr-view-pairs.sh, pr-view-wheel.sh, pr-view-stats.mjs,
      pr-view-first-routes.mjs) under explorations/performance-loop/.
  verdict:
    decision: accepted
    primary_metric: "time to the record's title on a pull request page opened from a cache that holds the record (pr-warm), pair ratio candidate/control at the 1.3x rough cut"
    reason: >-
      On a cached pull request page the title appears 683 ms after navigation on v0.12.0
      and 961 ms on main, pair ratios 1.33, 1.58, and 1.38, all three beyond the rough cut.
      v0.12.0 against main of 2026-11-12 shows no milestone difference. Across #369
      (84b2ffdce against 597a7c70e) the deciding pr-warm title is later in every pair but
      under the rough cut (1.14, 1.27, 1.18), so the bisect places the step at #369 by a
      context metric, a warm reload's title (112 to 204 ms, all three pairs beyond), and by
      the mechanism: #369's conversation first-paint hold. The cold-record path and the
      Pulls rows' milestones did not regress; the GET pull route's server time did, and is
      open.
    commit: c6aa02085
---
**Status:** Accepted.
A pull request page opened from a cache that already holds the record paints its title
about 280 ms later on main than on v0.12.0. The bisect places the step at #369
(`597a7c70e`), whose conversation first-paint hold keeps the header out of sight until
every text on the first screen has its rendered Markdown: across #369 a warm reload’s
title passes the rough cut in every pair, and the deciding pr-warm title is later in
every pair but under it.

## Why This Round

The owner found the pull request view slower after recent merges (bead `mb-g5wf`, epic
`mb-h36r`). This round asks whether a PR page or the Pulls tab is slower on main than on
v0.12.0 and than on main of a few days earlier, and which merge made a step if there is
one. It also leaves a benchmark that can repeat the comparison:
[pr-view.mjs](../pr-view.mjs) and its driver, described in
[Pull Request View Pairs](../README.md#pull-request-view-pairs).

## Method

[exp-099-protocol.txt](exp-099-protocol.txt) gives the builds, environment, steps,
metrics, decision rule, and stop conditions.
In short:

- Each build is a wheel built from `git archive` of its commit by
  [pr-view-wheel.sh](../pr-view-wheel.sh), installed with its pinned KPress into one
  environment, with bytecode compiled at every swap.
- [pr-view-pairs.sh](../pr-view-pairs.sh) runs five steps per round, each for both
  builds back to back, and alternates which build goes first by round.
  - `pr-fresh`: `/pull/470` on an empty cache.
  - `pr-store`: `/pull/487` with a Git store attached but the record never read.
  - `pr-warm`: `/pull/487` again with everything cached, on a new server and browser.
  - `pr-warm-reload`: the same document again from the same server.
  - `pulls-cold`, `pulls-warm`, and `pulls-warm-reload`: the same for `/pulls`.
- [pr-view.mjs](../pr-view.mjs) records, in every animation frame, the first frame at
  which each milestone holds.
  It also keeps the resource timings with their Server-Timing, and counts gh calls
  through a logging shim.
- [pr-view-stats.mjs](../pr-view-stats.mjs) gives medians, ranges, and the ratio of each
  back-to-back pair.
- The decision rule is the 1.3x rough cut, because other sessions kept the load at 5 to
  13: a metric moved when two or more of three pairs pass 1.3x and the medians agree.

Every series ran with GitHub’s core budget above 1859 and about 6 GB of free disk.

## Results

**v0.12.0 against main (the judged series, loads 7.8 to 13.6).**

| Step | Metric | v0.12.0 | main | Pair ratios |
| --- | --- | --- | --- | --- |
| pr-warm | title | 683 [640–694] | 961 [910–1014] | **1.33 / 1.58 / 1.38** |
| pr-warm | description final | 803 [760–813] | 961 [910–1014] | 1.12 / 1.33 / 1.20 |
| pr-warm | complete | 803 [760–813] | 998 [969–1086] | 1.19 / 1.43 / 1.24 |
| pr-warm-reload | title | 102 [100–103] | 126 [124–181] | 1.24 / 1.20 / 1.81 |
| pr-warm-reload | description final | 148 [141–153] | 126 [124–181] | 0.85 / 0.81 / 1.28 |
| pr-fresh | title | 1602 [1469–1646] | 1708 [1508–1742] | 1.07 / 1.19 / 0.92 |
| pr-store | title | 1627 [1581–1744] | 1798 [1608–1804] | 1.02 / 1.03 / 1.11 |
| pulls-cold | first row | 2491 [1488–2514] | 2499 [1507–2535] | 1.01 / 1.01 / 1.00 |
| pulls-warm | first row | 755 [583–876] | 780 [738–809] | 1.27 / 1.03 / 0.92 |
| pulls-warm-reload | first row | 103 [101–120] | 83 [79–91] | 0.78 / 0.88 / 0.69 |

Each cell is median [range] in ms from navigation start, n=3 per side.

**Bisect across #369** (`84b2ffdce` against `597a7c70e`, loads 8.6 to 11.8): a warm
reload’s title goes from 112 [110–114] to 204 [186–231] ms (1.82 / 2.03 / 1.69), and its
final description from 139 to 204 ms (1.59 / 1.66 / 1.30). The pr-warm title is later in
every pair, 739 to 926 ms (1.14 / 1.27 / 1.18), under the rough cut, so on the deciding
metric the bisect does not resolve; the reload and the mechanism below place the step.
pr-fresh and pr-store do not move, and route times do not change across #369.

**v0.12.0 against main of 2026-11-12** (`27ea216c7`, loads 7.9 to 10.3): no page
milestone differs; the pr-warm title is 637 [580–750] against 647 [617–696] ms.
The `GET pull` route’s server time does differ already; see Route Times.

**#369’s merge against main** (loads 6.9 to 10.8): the pr-warm title is unresolved, 839
to 917 ms (1.14 / 1.07 / 1.07). A warm reload’s title is much earlier on main, 231 to
123 ms (0.65 / 0.51 / 0.47), so the changes after #369 cut the long-running server’s
cost a lot.

### Why the Title Waits

When a document lands on the loading heading, `holdFirstPaint` in `pull-page.js` sets
`header: !delayed && bodyShows === "loading"`. The header then waits, out of sight, with
the body for the Markdown of every text on the first screen, at most
`DESCRIPTION_HOLD_MS`. On #487 those are four texts (the description, two issue
comments, and one review), requested `MARKDOWN_CONCURRENCY` (two) at a time.
From the record’s arrival to the title, v0.12.0 takes 24, 29, and 30 ms; it shows the
title at once and the description as plain text.
main takes 212, 228, and 258 ms: the last Markdown answer ends 150 to 170 ms after the
record, and the title follows 58, 59, and 87 ms after that.
On a freshly started server each first Markdown render takes 50 to 80 ms of server time,
against 1 to 5 ms (2 to 12 ms in the browser) on the warm reload, so the hold costs a
fresh server most. exp-080 accepted the hold for in-app clicks at 0 to 2 frames, and its
Limits section warned that a first screen with several texts waits a round trip per two
texts.

### Without a Browser

[pr-view-first-routes.mjs](../pr-view-first-routes.mjs) asks a fresh server on a warm
cache for what the page asks first (`exp-099-first-routes.jsonl`, four rounds per
build). The first `GET pull` takes 350 to 467 ms on v0.12.0, 368 to 391 before #369, and
359 to 372 on main; repeated calls take 4 to 21 ms.
The lazy import of the GitHub route modules, timed by a helper whose output stayed in
the measuring worktree’s `attic/` and is not in the samples, is 117 to 236, 121 to 148,
and 126 to 151 ms.
So in isolation the first `GET pull` costs the same in every build; in
the browser it does not (Route Times).

### Route Times

The protocol lists the first `GET pull`’s client and server time and `stacks`’s server
time among its metrics, and by its rule several moved (median [range] in ms, pair
ratios):

| Series | Step | Metric | control | candidate | Pair ratios |
| --- | --- | --- | --- | --- | --- |
| v0.12.0 → main | pr-store | `pull` srv | 230 [213–239] | 330 [316–348] | 1.32 / 1.44 / 1.63 |
| v0.12.0 → main | pr-warm | `pull` srv | 243 [241–261] | 337 [330–343] | 1.42 / 1.36 / 1.29 |
| v0.12.0 → main | pr-fresh | `pull` srv | 50 [48–51] | 63 [58–69] | 1.39 / 1.33 / 1.14 |
| v0.12.0 → main | pr-warm-reload | `pull` client | 11 [10–12] | 29 [27–29] | 2.64 / 2.42 / 2.70 |
| v0.12.0 → main | pr-warm-reload | `pull` srv | 10 [8–10] | 26 [24–26] | 2.67 / 2.58 / 2.87 |
| v0.12.0 → main | pr-warm-reload | `stacks` srv | 16 [15–20] | 30 [28–31] | 2.07 / 1.51 / 1.73 |
| v0.12.0 → main | pulls-cold | `pulls` srv | 43 [41–43] | 57 [57–58] | 1.33 / 1.37 / 1.34 |
| v0.12.0 → Nov 12 | pr-store | `pull` srv | 224 [214–248] | 319 [305–366] | 1.48 / 1.42 / 1.42 |

The pr-store and pr-warm growth was there by 2026-11-12, before #369. On the first
requests the route answers while the page’s other first requests run, and in isolation
it costs the same in every build, so the growth may be contention with more work at page
start, or more work in the route since v0.12.0; this round does not say which.
None of it decides the title’s wait, which starts once the record has arrived.
It is open, for a round of its own.

### What Did Not Move

- The cold-record path, with no cache (pr-fresh) and with a store attached (pr-store).
- The Pulls rows’ first row, cold and warm.
- On a long-running server, main’s final description is no later than v0.12.0’s: 126
  against 148 ms, pair ratios 0.85 / 0.81 / 1.28, none past either cut.

The Diff summary (#478) and the Pulls change line (#491) arrived after v0.12.0, so they
have no baseline to regress from.
main’s figures for them are in the samples: on pr-store the loading box shows at 1849 ms
and the summary at 3432 ms.
`exp-099-pairs-pulls-pf.jsonl` compares main with `227b5bab5` (the Pulls store-first
change, #522) on Pulls only: the last cold change line goes from 27197 to 8112 ms (0.31
/ 0.30 / 0.30).

## Deviation

The round broke three of the loop’s registration rules:

- **The protocol was not committed before the measurements.** It was written after a
  single-run screen and a first series had run, and every judged and bisect series ran
  (18:06 to 18:30 UTC) before its first commit, with this record (18:42 UTC). That the
  series ran under it rests on the measuring agent’s report, not on history.
  The first series ran without bytecode compilation and was discarded, because every
  wheel swap made the first requests recompile the package, which costs a larger build
  more.
- **The analysis was not registered.** The protocol names no analysis script by sha256,
  so the record has no `method.analysis`, and the committed
  [pr-view-stats.mjs](../pr-view-stats.mjs) is not byte for byte the script that ran.
- **Builds it lists were not measured:** `c098e6a82` (main of 2026-11-14) and the #478
  bisect pair `509e0ed2f` and `1dcbe93f1`, because the step was found at #369.

So the round is exploratory evidence for the step, not a pre-registered test; exp-100,
which tests a fix with this benchmark, registered its protocol and analysis first.

The committed scripts differ from the ones that ran only in comments, formatting, and
one wrapped line; the first series alone used an earlier recorder with a gh-only shim
passed through environment variables.

## Limits

- **Headless only, on a loaded machine.** The rough cut resolves effects above about
  1.3x; smaller ones are unresolved.
- **One pull request for the warm and store cases** (#487, four texts on its first
  screen). A first screen with only the description waits less.
- **The pr-warm first `GET pull`’s client time** (425 to 513 ms) passes 1.3x in one pair
  of three, so it is not a result on its own; its server time is (Route Times).
- **`complete` is not the same milestone in both builds:** main’s includes the Diff
  summary, which v0.12.0 does not have.
- **The Pulls store-first comparison** (`227b5bab5`) is a sibling of main at #513, not a
  descendant: the two share 4eb299fd1, so it also lacks #513, which is on the Pulls
  path.
- **Clicking a Pulls row to open a PR** was not measured here; exp-080’s transition
  scenario covers that path.
- **The live repository moves.** The open pull requests changed between series, so Pulls
  figures compare only within one series.
- The server logs, which hold local paths, stayed in the measuring worktree’s `attic/`.

## Next

Three changes follow, tracked in `mb-g5wf`:

1. Paint the header at once and hold only the body.
   This undoes `cf117163a`’s change-once rule, so it waits for the owner’s decision.
2. Request the held first screen’s Markdown all at once instead of two at a time, which
   saves a Markdown round trip on #487.
3. Warm KPress and the GitHub routes’ lazily imported modules at server start, off the
   event loop: an older cost, the 350 to 500 ms first `GET pull`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
