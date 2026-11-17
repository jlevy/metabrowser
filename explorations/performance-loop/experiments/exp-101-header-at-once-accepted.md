---
title: Painting a Held Page's Header at Once Brings the Title Back to the Record's Arrival
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-101
  title: Painting a Held Page's Header at Once Brings the Title Back to the Record's Arrival
  date: "2026-11-17"
  hypotheses:
    - H121
  subject:
    corpus: >-
      exp-099's subject: a clean linked worktree of this repository at 4eb299fd1, served as a
      folder in checkout mode against the live jlevy/metabrowser repository; pull requests
      #470, #487 (four texts on its first screen), and #514 (store preparation only).
    corpus_files: 1875
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0 arm64; one-minute load average 14 to 52 from other sessions
    browser: Headless Chrome 152 over the DevTools Protocol, a fresh profile per server, visibilityState visible
    viewport: 1400x813
    cold: true
  method:
    runs_per_condition: 5
    interleaved: true
    control: metab 0.12.1.dev1621+c6aa0208 (main at #513, c6aa02085), from a wheel built by pr-view-wheel.sh
    candidate: >-
      metab 0.12.1.dev1626+51e06a4f3 (51e06a4f3: the control with the pr-view benchmark,
      the exp-099 and exp-100 records, and the header painted at once), from a wheel built
      by pr-view-wheel.sh into the same environment
    protocol:
      path: exp-101-protocol.txt
      sha256: 5429c7f4fcb24948c57aa82927e634c61d25a254400a3df1f99a6ea520962d36
    record: exp-101-pairs.jsonl; read it with pr-view-stats.mjs --control control --candidate candidate
  results:
    - metric: pr-warm.title_after_pull_ms
      control_median: 232
      candidate_median: 33
      control_range: [207, 275]
      candidate_range: [31, 35]
      change_pct: -85.8
      overlapping: false
    - metric: pr-warm.title_ms
      control_median: 887
      candidate_median: 677
      control_range: [827, 998]
      candidate_range: [620, 718]
      change_pct: -23.7
      overlapping: false
    - metric: pr-warm.description_final_ms
      control_median: 887
      candidate_median: 905
      control_range: [827, 998]
      candidate_range: [828, 938]
      change_pct: 2
      overlapping: true
    - metric: pr-warm.complete_ms
      control_median: 905
      candidate_median: 928
      control_range: [858, 1013]
      candidate_range: [854, 953]
      change_pct: 2.5
      overlapping: true
    - metric: pr-warm-reload.title_after_pull_ms
      control_median: 48
      candidate_median: 18
      control_range: [44, 52]
      candidate_range: [12, 30]
      change_pct: -62.5
      overlapping: false
    - metric: pr-warm-reload.title_ms
      control_median: 130
      candidate_median: 96
      control_range: [115, 136]
      candidate_range: [85, 98]
      change_pct: -26.2
      overlapping: false
    - metric: pr-warm-reload.description_final_ms
      control_median: 130
      candidate_median: 122
      control_range: [115, 136]
      candidate_range: [118, 128]
      change_pct: -6.2
      overlapping: true
    - metric: pr-fresh.title_ms
      control_median: 1798
      candidate_median: 1681
      control_range: [1446, 1887]
      candidate_range: [1485, 1810]
      change_pct: -6.5
      overlapping: true
    - metric: pr-fresh.description_final_ms
      control_median: 2977
      candidate_median: 2810
      control_range: [2407, 3053]
      candidate_range: [2457, 2911]
      change_pct: -5.6
      overlapping: true
    - metric: pr-store.title_ms
      control_median: 1836
      candidate_median: 1812
      control_range: [1744, 2051]
      candidate_range: [1694, 2347]
      change_pct: -1.3
      overlapping: true
    - metric: pr-store.description_final_ms
      control_median: 3498
      candidate_median: 3464
      control_range: [3275, 3822]
      candidate_range: [3134, 4202]
      change_pct: -1
      overlapping: true
    - metric: pr-warm.pull_ms
      control_median: 446
      candidate_median: 450
      control_range: [429, 459]
      candidate_range: [419, 465]
      change_pct: 0.9
      overlapping: true
  complexity:
    lines_changed: 114
    new_dependencies: []
    new_failure_modes:
      - An unlabelled pull request whose record lands after the quiet period, over loading blocks that had shown, now moves its tab bar and the blocks up by the labels row before the body shows, where before the move waited for the body.
    notes: >-
      pull-page.js and styles.css lose 100 lines and gain 14: the held header, its inert
      tab column and focus hand-back, the cold page kept unseen for it, and the stack keys'
      wait go.
  verdict:
    decision: accepted
    primary_metric: "pr-warm title_after_pull, the title's first frame minus the first GET pull's response end, pair ratio candidate/control under 1/1.3 in at least 3 of 5 pairs"
    reason: >-
      On #487 from a warm cache on a fresh server, the title came 232 ms after the record on
      main and 33 ms with the header painted at once, pair ratios 0.12, 0.14, 0.15, 0.16,
      and 0.13, all five under 1/1.3; v0.12.0 took 24 to 30 ms (exp-099). The title from
      navigation went from 887 to 677 ms, and on a warm reload from 130 to 96 ms. No guard
      passed 1.3x in any pair.
    commit: 51e06a4f3
---
**Status:** Accepted.
With the header painted as soon as the record is in hand, a cached pull request’s title
shows 33 ms after the record instead of 232 ms, close to v0.12.0’s 24 to 30 ms, and the
conversation shows no later than before.

## Why This Round

[exp-099](exp-099-pr-view-regression-is-369-first-paint-hold.md) found that a cached
pull request page showed its title about 280 ms later than v0.12.0, because a first
paint held over the loading page kept the loading heading too (`cf117163a`, review D1’s
change-once rule), so the title waited for the Markdown of every text on the first
screen. [exp-100](exp-100-held-markdown-at-once-rejected.md) showed that asking for that
Markdown at once does not shorten the wait.
The owner decided for painting the header first.
H121 predicts that the title then follows the record as closely as on v0.12.0, while the
body still waits for its Markdown.

## Method

[exp-101-protocol.txt](exp-101-protocol.txt) was registered and pushed before the first
timed run, with the scripts and the analysis by sha256.
[pr-view-pairs.sh](../pr-view-pairs.sh) ran five rounds of `pr-fresh`, `pr-store`,
`pr-warm`, and `pr-warm-reload`, each step for both builds back to back, the leading
build alternating by round; [pr-view-stats.mjs](../pr-view-stats.mjs) paired the runs by
the round each recorded.
GitHub’s core budget stayed above 2288 and free disk at 4 GB.

## Results

| Step | Metric (ms) | control | candidate | Pair ratios |
| --- | --- | --- | --- | --- |
| pr-warm | **title after the record** | 232 [207–275] | 33 [31–35] | **0.12 / 0.14 / 0.15 / 0.16 / 0.13** |
| pr-warm | title | 887 [827–998] | 677 [620–718] | 0.72 / 0.78 / 0.69 / 0.82 / 0.76 |
| pr-warm | description final | 887 [827–998] | 905 [828–938] | 0.94 / 1.03 / 0.89 / 1.09 / 0.99 |
| pr-warm | complete | 905 [858–1013] | 928 [854–953] | 0.94 / 1.04 / 0.85 / 1.08 / 0.99 |
| pr-warm-reload | title after the record | 48 [44–52] | 18 [12–30] | 0.38 / 0.29 / 0.26 / 0.52 / 0.68 |
| pr-warm-reload | title | 130 [115–136] | 96 [85–98] | 0.63 / 0.74 / 0.73 / 0.83 / 0.75 |
| pr-fresh | title | 1798 [1446–1887] | 1681 [1485–1810] | 1.01 / 0.96 / 0.90 / 1.03 / 0.92 |
| pr-store | title | 1836 [1744–2051] | 1812 [1694–2347] | 1.13 / 1.14 / 1.02 / 0.92 / 0.99 |

Each cell is median [range], n=5 per side; “after the record” is from the first
`GET pull`’s response end.

- **The deciding metric** moved in every pair, and the candidate’s 33 ms is a few ms
  above v0.12.0’s 24 to 30 ms (exp-099, another series on the same machine).
- **The body did not move:** the description final and complete stayed within 1.1x in
  every pair, since the conversation still waits for its Markdown as before.
- **The cold-record path did not move:** pr-fresh and pr-store wait on GitHub, and their
  title was within 1.14x in every pair.
- No guard passed 1.3x in any pair.

## Layout

This series does not measure layout.
The real-Chrome header test (`tests/dom/github-pull-header-chrome.mjs`, `cold-landing`)
checks it, at 560 and 360 px, labelled and unlabelled.
A record that lands within the quiet period shows its header at once, with the
conversation still held, and its tab bar never moves.
A slower read still shows the cold header, rows held, and an unlabelled pull request
then moves its tab bar up by the labels row as its record lands, as before.
The difference is that this now happens before the body shows, rather than with it.

## Limits

- **A loaded machine** (load average 14 to 52): the rough cut resolves the deciding
  metric’s 7x change, not small guard movements.
- **One pull request**, with four texts on its first screen.
- **Headless Chrome only.**

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
