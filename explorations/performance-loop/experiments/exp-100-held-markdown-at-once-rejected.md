---
title: Asking for a Held First Screen's Markdown at Once Does Not Shorten the Hold
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-100
  title: Asking for a Held First Screen's Markdown at Once Does Not Shorten the Hold
  date: "2026-11-17"
  hypotheses:
    - H120
  subject:
    corpus: >-
      exp-099's subject: a clean linked worktree of this repository at 4eb299fd1, served as a
      folder in checkout mode against the live jlevy/metabrowser repository; pull requests
      #470, #487 (four texts on its first screen), and #514 (store preparation only).
    corpus_files: 1875
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0 arm64; one-minute load average 16 to 43 from other sessions
    browser: Headless Chrome 152 over the DevTools Protocol, a fresh profile per server, visibilityState visible
    viewport: 1400x813
    cold: true
  method:
    runs_per_condition: 5
    interleaved: true
    control: metab 0.12.1.dev1621+c6aa0208 (main at #513, c6aa02085), from a wheel built by pr-view-wheel.sh
    candidate: >-
      metab 0.12.1.dev1623+b79bdafa (b79bdafa6: the control with the pr-view benchmark and
      requestMarkdown's `{now: true}` for the held first screen's texts), from a wheel built
      by pr-view-wheel.sh into the same environment
    protocol:
      path: exp-100-protocol.txt
      sha256: 24b01b38252b53098160d48a1188e42bd037a99a6724b75ead8148be23593cc9
    record: exp-100-pairs.jsonl; read it with pr-view-stats.mjs --control control --candidate candidate
  results:
    - metric: pr-warm.title_after_pull_ms
      control_median: 233
      candidate_median: 230
      control_range: [216, 241]
      candidate_range: [220, 253]
      change_pct: -1.3
      overlapping: true
    - metric: pr-warm.markdown_after_pull_ms
      control_median: 141
      candidate_median: 154
      control_range: [113, 166]
      candidate_range: [136, 192]
      change_pct: 9.2
      overlapping: true
    - metric: pr-warm.title_ms
      control_median: 852
      candidate_median: 863
      control_range: [805, 889]
      candidate_range: [813, 880]
      change_pct: 1.3
      overlapping: true
    - metric: pr-warm.description_final_ms
      control_median: 889
      candidate_median: 863
      control_range: [805, 916]
      candidate_range: [813, 880]
      change_pct: -2.9
      overlapping: true
    - metric: pr-warm.complete_ms
      control_median: 950
      candidate_median: 898
      control_range: [830, 1061]
      candidate_range: [832, 939]
      change_pct: -5.5
      overlapping: true
    - metric: pr-warm-reload.title_ms
      control_median: 125
      candidate_median: 113
      control_range: [121, 136]
      candidate_range: [109, 164]
      change_pct: -9.6
      overlapping: true
    - metric: pr-warm-reload.title_after_pull_ms
      control_median: 43
      candidate_median: 43
      control_range: [37, 44]
      candidate_range: [41, 47]
      change_pct: 0
      overlapping: true
    - metric: pr-fresh.title_ms
      control_median: 1646
      candidate_median: 1574
      control_range: [1553, 1874]
      candidate_range: [1459, 1706]
      change_pct: -4.4
      overlapping: true
    - metric: pr-fresh.description_final_ms
      control_median: 2625
      candidate_median: 2484
      control_range: [2529, 3015]
      candidate_range: [2390, 2810]
      change_pct: -5.4
      overlapping: true
    - metric: pr-store.title_ms
      control_median: 1758
      candidate_median: 1793
      control_range: [1658, 2059]
      candidate_range: [1766, 1867]
      change_pct: 2
      overlapping: true
    - metric: pr-store.description_final_ms
      control_median: 3338
      candidate_median: 3311
      control_range: [3110, 3694]
      candidate_range: [3269, 3479]
      change_pct: -0.8
      overlapping: true
    - metric: pr-warm.pull_ms
      control_median: 437
      candidate_median: 428
      control_range: [405, 456]
      candidate_range: [412, 447]
      change_pct: -2.1
      overlapping: true
  complexity:
    lines_changed: 79
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      The candidate's change to pull-page.js (b79bdafa6) is not landed. What lands is the
      record and pr-view-stats.mjs's hold metrics.
  verdict:
    decision: rejected
    primary_metric: "pr-warm title_after_pull, the title's first frame minus the first GET pull's response end, pair ratio candidate/control under 1/1.3 in at least 3 of 5 pairs"
    reason: >-
      On #487 from a warm cache on a fresh server, the held title came 233 ms after the
      record on the control and 230 ms on the candidate, pair ratios 0.99, 1.08, 0.99, 1.13,
      and 0.95: none under 1/1.3, so the change is rejected as registered. The four
      Markdown requests started at the same times in both builds, and the title came 41 to
      117 ms after the last answer in every run, so the wait is not in the requests.
---
**Status:** Rejected.
Asking for the held first screen’s texts at once, past `MARKDOWN_CONCURRENCY`, leaves a
cached pull request’s held title where it was: 233 ms after the record on main, 230 ms
with the change.

## Why This Round

[exp-099](exp-099-pr-view-regression-is-369-first-paint-hold.md) found that a cached
pull request page holds its title, with the conversation, until every text on its first
screen has its Markdown, and that the texts were asked for two at a time
(`MARKDOWN_CONCURRENCY` in `pull-page.js`). On #487 the four requests started 7, 30, 73,
and 102 ms after the record.
H120 predicted that asking for the held texts at once would save one Markdown round
trip, 50 to 80 ms on a fresh server.

## Method

[exp-100-protocol.txt](exp-100-protocol.txt) was registered and pushed (as `cb5fe1b56`
on `claude/pr-markdown-held-at-once`) before the first timed run.
It gives the builds, the series, the decision rule, and the analysis script by sha256.
[pr-view-pairs.sh](../pr-view-pairs.sh) ran five rounds of `pr-fresh`, `pr-store`,
`pr-warm`, and `pr-warm-reload`, each step for both builds back to back, the leading
build alternating by round.
[pr-view-stats.mjs](../pr-view-stats.mjs) at the registered sha256 read the samples.
The registered scripts are kept in history: `pr-view.mjs`, `pr-view-pairs.sh`, and
`pr-view-wheel.sh` are #524’s first commit’s (`2cbf65b2b`), and `pr-view-stats.mjs` is
that commit’s with this round’s hold metrics, as at `b79bdafa6`. The measured candidate
and the registration commit are kept under the tag `exp-100-candidate`: it names
`cb5fe1b56`, which registered the protocol, and whose parent `b79bdafa6` is the
candidate.
All four committed scripts have changed since for #524’s review; the committed
`pr-view-stats.mjs` prints the same figures from these samples, which carry no round.
GitHub’s core budget stayed above 3353 and free disk at 5 GB.

## Results

| Step | Metric | control | candidate | Pair ratios |
| --- | --- | --- | --- | --- |
| pr-warm | title after the record | 233 [216–241] | 230 [220–253] | 0.99 / 1.08 / 0.99 / 1.13 / 0.95 |
| pr-warm | last Markdown after the record | 141 [113–166] | 154 [136–192] | 1.58 / 0.96 / 1.08 / 1.16 / 1.10 |
| pr-warm | title | 852 [805–889] | 863 [813–880] | 1.02 / 1.09 / 0.97 / 0.95 / 0.98 |
| pr-warm-reload | title | 125 [121–136] | 113 [109–164] | 1.21 / 0.84 / 0.93 / 1.03 / 0.89 |
| pr-fresh | title | 1646 [1553–1874] | 1574 [1459–1706] | 0.91 / 0.99 / 0.89 / 1.01 / 0.86 |
| pr-store | title | 1758 [1658–2059] | 1793 [1766–1867] | 0.87 / 1.02 / 1.08 / 0.90 / 1.06 |

Each cell is median [range] in ms, n=5 per side; “after the record” is from the first
`GET pull`’s response end.
No guard passed 1.3x in more than one pair.

### Why Nothing Moved

The Markdown requests went out at the same times in both builds.
From the record’s arrival, on pr-warm:

| Request | control start | candidate start | server time, both builds |
| --- | --- | --- | --- |
| 1 (the description) | 5–7 ms | 5–7 ms | 51–82 ms |
| 2 | 26–30 ms | 23–28 ms | 45–78 ms |
| 3 | 59–89 ms | 61–74 ms | 32–85 ms |
| 4 | 86–99 ms | 72–108 ms | 19–73 ms |

The change cannot help, for two reasons:

- **Only two texts are on the first screen when the hold first looks.** It measures the
  screen with every text still plain, and the plain description is long.
  Those two were already in flight together in both builds (requests 1 and 2 overlap in
  every run). The third and fourth texts are `FIRST_SCREEN_AHEAD` texts past the screen,
  which the change still queues; in both builds the third starts as the first answers,
  and the fourth as the second answers.
- **The hold does not end when the answers come.** On pr-warm the title, which is the
  hold’s release, came 113 to 183 ms after the two waited texts were answered, and 41 to
  117 ms after the last of all four answers, in all ten runs.
  In three of them the description was still plain at the release (`description_final`
  15 to 64 ms after the title), though its Markdown had been answered at 58 to 74 ms.
  On the warm reload, where the browser already holds the page’s assets, the title came
  37 to 47 ms after the record.

So the wait sits in the browser after the answers.
By inference, not measured: a text’s Markdown is inserted only once KPress’s stylesheets
for it have loaded (`Promise.all([inertReady, documentStyles])` in `pull-page.js`), and
`documentStyles` starts loading on the first answer, so on a fresh browser profile the
insertion waits for that load, or the hold ends at its bound.
That asset load, not the server’s renders or the request queue, is the next candidate
for the conversation’s wait.
The title’s wait goes away with the header painted at once (exp-101).

## Limits

- **A loaded machine.** The load average was 16 to 43, so effects under 1.3x are
  unresolved; the hold’s ranges overlap entirely.
- **One pull request**, with four texts on its first screen.
- **A fresh server per run.** On a long-running server (pr-warm-reload) a render takes 1
  to 9 ms, and the hold is 37 to 47 ms in both builds.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
