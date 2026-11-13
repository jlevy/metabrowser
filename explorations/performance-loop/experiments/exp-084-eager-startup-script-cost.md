---
title: The 220 KB eager-script ceiling holds as a rough cut
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-084
  title: The 220 KB eager-script ceiling holds as a rough cut
  date: "2026-11-12"
  hypotheses:
    - H107
  subject:
    corpus: >-
      this repository's docs/, src/, and README.md at 27ea216c, copied into one folder with
      no Git directory, served as a folder page at /view/
    corpus_files: 468
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0
    browser: headless Chrome 152.0.7977.83 driven through the DevTools Protocol
    viewport: "1280x900"
    cold: true
  method:
    runs_per_condition: 30
    interleaved: true
    control: >-
      src/metabrowser at 27ea216c, whose 20 startup scripts transfer 178,592 bytes (174 KB)
    candidate: >-
      the same scripts with every comment followed by 54% of its length of added comment,
      225,531 bytes (220 KB), tokens checked equal to the control's
    record: >-
      exp-084-eager-startup-script-cost-samples.jsonl, nine series named by each record's
      series field; replay one with tier-probe.mjs --summarize FILE --series NAME. The
      ceiling-local, ceiling-near, and ceiling-far series are the validation. Loaded host
      throughout (load average 32-109 on 10 cores), one series per path, no A/A series:
      rough-cut evidence under the README's tolerance rule
  results:
    - metric: first_row_ms_loopback_220kb
      control_median: 92.4
      candidate_median: 99.4
      control_range: [86.2, 121.5]
      candidate_range: [88.2, 139.2]
      change_pct: 7.6
      overlapping: true
    - metric: first_row_ms_10ms_link_220kb
      control_median: 111.7
      candidate_median: 110.8
      control_range: [94.6, 168.9]
      candidate_range: [101.1, 200.3]
      change_pct: -0.9
      overlapping: true
    - metric: first_row_ms_80ms_link_220kb
      control_median: 514.1
      candidate_median: 533.1
      control_range: [509.2, 520.0]
      candidate_range: [526.0, 540.4]
      change_pct: 3.7
      overlapping: false
  verdict:
    decision: accepted
    primary_metric: first_row_ms_loopback_220kb
    reason: >-
      Accepted as a rough cut. Paired against main, the 220 KB build's first row was 1.07x
      (1.03-1.14) on loopback, 0.99x (0.95-1.11) on a 10 ms link, and 1.04x (1.03-1.04) on
      an 80 ms link: far inside the 1.3x rough cut, with medians under the careful 1.1x and
      intervals that reach past it. It sets startup_script_transfer_kb = 220. It does not
      establish the careful 1.1x, which needs a quiet host, two series per path, and an A/A
      series.
---
## What This Records

[The eager startup-script cost](../../../docs/project/research/research-2026-11-12-eager-startup-script-cost.md)
is the write-up: what a transferred kilobyte of startup script costs, where the cost
goes, and why `startup_script_transfer_kb` is 220. This record carries its samples and
its verdict, so the numbers beside that constant can be regenerated.

The samples are one record per load.
The six series taken before the instrument moved into `tier-probe.mjs` named some fields
differently (`bgParseMs`, `startupScriptsLastEndMs`, a flat cost record); they are
projected onto the probe’s names with no value changed.
Each record keeps the timings, byte counts, and trace sums the summary reads, and drops
the per-script lists and layout shifts.

```shell
node explorations/performance-loop/tier-probe.mjs \
  --summarize explorations/performance-loop/experiments/exp-084-eager-startup-script-cost-samples.jsonl \
  --series ceiling-local
```

## The Validation

Each validation series loaded `main` and the 220 KB build back to back, alternating
which went first, so both builds took each place in a pair equally often.
First row, as the paired median with the 95% bootstrap interval the probe prints:

| Series | Path | Pairs | Load | Difference | Ratio |
| --- | --- | ---: | --- | --- | --- |
| `ceiling-local` | loopback | 30 | 72-92 | +6.6 ms (+2.8 to +12.4) | 1.069 (1.030 to 1.138) |
| `ceiling-near` | 10 ms, 100 Mbps | 20 | 67-76 | −0.7 ms (−5.2 to +11.3) | 0.993 (0.954 to 1.110) |
| `ceiling-far` | 80 ms, 20 Mbps | 10 | 56-68 | +19.4 ms (+16.5 to +20.4) | 1.038 (1.032 to 1.040) |

That is the evidence for 220 KB. The
[tolerance rule](../README.md#comparing-a-candidate-with-the-previous-release) reserves
the careful 1.1x for a quiet machine; these ran on a loaded one, one series per path,
with no A/A series to show the noise between two identical builds.
So they are a rough cut: far inside 1.3x, medians under 1.1x, upper ends past it on
loopback and the 10 ms link.

## The Slopes

The slope series loaded `main` (`control`), the comment-stripped build (`stripped`,
104,937 bytes), the comment-doubled build (`padded`, 261,266 bytes), and in two of them
`main` sent uncompressed (`nogzip`). A slope is the median, over the pairs of one
series, of the doubled build’s first row minus the stripped build’s, divided by their
152.7 KB difference.
It is a paired median, so it is not the difference of the two builds’ medians against
`main`. Replay it with `--control stripped`:

| Series | Path | Pairs | ms per transferred KB | Places of the two builds |
| --- | --- | ---: | --- | --- |
| `local-cold` | loopback | 30 | +0.184 (+0.080 to +0.230) | stripped always second of three |
| `near-cold` | 10 ms, 100 Mbps | 12 | +0.276 (+0.062 to +0.403) | both second or third of four |
| `far-cold` | 80 ms, 20 Mbps | 10 | +0.323 (+0.300 to +0.334) | both second or third of four |
| `cpu4-cold` | loopback, CPU 4x | 12 | +0.016 (−0.034 to +0.096) | stripped always second of three |

Those series reversed the order every other pair, which balances the places of two
builds and not of more.
In the three-build series the stripped build always loaded second, and in the four-build
series the stripped and doubled builds never loaded first or last, so their comparisons
with `main` carry any effect of place.
The probe now rotates the order instead and prints how often each build took each place.
The two-build series are balanced.
One of them (`local-gzip`) shows the first load of a pair 14 ms slower than the second,
an effect that pairing cancels and an unbalanced series does not.

The slopes chose 220 KB as the candidate to measure; they are not its evidence.
On the 10 ms link the slope predicted +12.8 ms for the 220 KB build, and its direct
measurement was −0.7 ms; on the 80 ms link it predicted +14.7 ms, and the measurement
was +19.4 ms.

## Not Established

- The careful 1.1x: it needs a quiet host, at least 24 pairs per path in two independent
  series, and an A/A series.
- A real SSH tunnel, a visible window, `WKWebView`, and the repository-shaped corpus, as
  the brief’s Methodology lists.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
