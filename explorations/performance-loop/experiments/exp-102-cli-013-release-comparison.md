---
title: CLI 0.13.0 Startup Under Matched HTTP Readiness
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-102
  title: CLI 0.13.0 Startup Under Matched HTTP Readiness
  date: "2026-11-22"
  hypotheses:
    - H57
  subject:
    corpus: Public project-10, tree-fe8cdefa, corpus shape 2
    corpus_files: 246760
    corpus_dirs: 12860
    host_cpu: Intel Xeon 6975P-C, 4 vCPUs
    host_system: Ubuntu 24.04 GitHub-hosted image 20261116.133.1, Linux 7.0.0-1014-aws, CPython 3.13
    browser: Headed Google Chrome 157.0.8103.78 on Xvfb
    viewport: 1600x1040
    cold: true
  method:
    runs_per_condition: 5
    interleaved: true
    control: "metab 0.12.0, exact wheel from v0.12.0 (87b8ec812774bb12a4d9f5f29901719b8b66d323)"
    candidate: "metab 0.13.0.dev3019+29f9f8c, exact wheel from 29f9f8c36661ffde18d02990873771088522e662"
    bytecode: cached
    protocol:
      path: exp-102-protocol.txt
      sha256: f51040778437a08f2d93daa21051a2305a4b4b9f14284c457f3e71340b00d93c
    record: "../results/runs.jsonl labels exp-102-cli-013-http-ready-v0120 and exp-102-cli-013-http-ready-candidate"
  results:
    - metric: browser_first_row_ms
      control_median: 144
      candidate_median: 225
      control_range: [112, 301]
      candidate_range: [211, 230]
      overlapping: true
    - metric: browser_ttfb_ms
      control_median: 17
      candidate_median: 17
      control_range: [15, 19]
      candidate_range: [14, 26]
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 88
      candidate_median: 116
      control_range: [88, 328]
      candidate_range: [96, 116]
      overlapping: true
    - metric: browser_dom_content_loaded_ms
      control_median: 157
      candidate_median: 240
      control_range: [121, 329]
      candidate_range: [224, 244]
      overlapping: true
    - metric: browser_startup_script_last_response_ms
      control_median: 134
      candidate_median: 213
      control_range: [105, 155]
      candidate_range: [199, 217]
      overlapping: false
    - metric: browser_first_row_render_ms
      control_median: 1
      candidate_median: 4
      control_range: [1, 3]
      candidate_range: [3, 4]
      overlapping: true
    - metric: browser_spawn_to_first_row_ms
      control_median: 2644
      candidate_median: 2764
      control_range: [2599, 11918]
      candidate_range: [2738, 2782]
      overlapping: true
    - metric: backend_first_row_ms
      control_median: 10
      candidate_median: 10
      control_range: [9, 12]
      candidate_range: [9, 11]
      overlapping: true
  verdict:
    decision: rejected
    primary_metric: browser_first_row_ms
    commit: 29f9f8c36661ffde18d02990873771088522e662
    reason: >-
      Five candidate runs passed every absolute budget after matching HTTP readiness.
      Four of five pairs still exceeded the 1.3× rough-cut first-row tolerance. The exact release
      dependencies differ, so the software comparator declined the comparison. A separate
      four-pair check with the optional-font change reproduced the residual delay and
      lacks the fifth required pair.
---
# Exp-102: CLI 0.13.0 Startup Under Matched HTTP Readiness

In five runs after a matched HTTP readiness check, the 0.13.0 candidate drew its first
directory row in 211–230 ms.
It passed every absolute browser budget.
Four of the five candidate/control pairs were slower than the 1.3× rough-cut release
tolerance. An earlier socket-ready series had exceeded the 350 ms limit because the
candidate started accepting TCP connections before its app could answer them.
The control begins listening after app startup.
[Matched-HTTP run](https://github.com/jlevy/metabrowser/actions/runs/45113677625)

## Method and Artifact Identity

The run used the same public project-10 corpus within each paired series.
Its inventory counter saw 246,760 files and 12,860 directories.
Each build was installed into its own exact locked environment with compiled bytecode.
The control wheel SHA-256 is
`5f080045c5416c82b007996f86e3bfd9f8309c98e0331c833379b7cd584332bc` and the candidate’s
is `9b785d13c3bf7f00fc158593e8252dc20ea5853afd184dcfd46be39943af9cfb`. The only runtime
dependency change beyond Metabrowser was KPress 0.3.5 to 0.3.9. Both wheels pin their
own version. The stock comparator recorded its refusal to compare different environment
fingerprints. It would be incorrect to force either wheel into the other’s environment.

The Chrome driver at `65f3469813210c18d46b12678e893305dc1f07a3` started its trusted
input sentinel as soon as the measured document body and input recorder were available.
It verified the exact navigation URL and the sentinel hit target before dispatch.
The application, probe, and recorder stayed at the measured revision.
All ten socket-ready profiles were visible throughout.
Control interaction coverage ranged from 87.0% to 98.5%. Candidate coverage ranged from
94.8% to 95.1%. Every control met all hard budgets.
Each candidate missed exactly one hard budget, `first_row_ms`.
[Normalized browser ledger](../results/runs.jsonl) ·
[Diagnostic driver](https://github.com/jlevy/metabrowser/commit/65f3469813210c18d46b12678e893305dc1f07a3)

## Socket-Ready Attribution

| Pair | Control first row, ms | Candidate first row, ms | Candidate / control | Control spawn to row, ms | Candidate spawn to row, ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 242 | 697 | 2.88 | 10,336 | 1,963 |
| 2 | 144 | 719 | 4.99 | 2,572 | 1,991 |
| 3 | 141 | 733 | 5.20 | 2,579 | 2,004 |
| 4 | 131 | 720 | 5.50 | 2,592 | 1,991 |
| 5 | 132 | 765 | 5.80 | 2,592 | 2,044 |

Time to the first HTTP response byte accounts for most of the first-row gap.
It was 12–22 ms on the control and 488–547 ms on the candidate.
The client spent 1–4 ms rendering the first row on the control and 2–3 ms on the
candidate. In pair 3, the 503 ms response-byte difference accounts for 85% of the 592 ms
first-row difference.
The candidate also transfers more startup script bytes, 220 KB versus 174 KB.

Chrome navigation on the candidate started 1,266–1,279 ms after process spawn.
In four control runs it started 2,428–2,461 ms after spawn.
The first control started at 10,094 ms and is retained as an outlier.
The backend harness separately recorded HTTP readiness at medians of 1.587 s and 1.670 s
from spawn.
It requires an HTTP response from `/api/tree?depth=0` before it starts timing
rows. It never measures the browser shell.
For cold browser measurements, the port-reservation fix makes a successful TCP connect
an earlier event on the candidate.
It allows traffic to queue while the app completes startup.
The regular CLI auto-open path waits for HTTP. The subsequent series timed both builds
after their first successful HTTP response.
[Port-reservation change](https://github.com/jlevy/metabrowser/commit/b86e837257149d7338bf6bb8f6c543fbf551c01b)

## Backend Correctness and Incomplete Runs

All five hosted attempts completed five backend pairs.
The first-row median was 9 ms on each build in the first run and 10 ms on each build in
the next three. In the optional-font series the control took 9 ms and the candidate 10
ms. Required fields and ordered rows matched in all five comparisons.
The raw backend verdict records nine tally differences.
Registry schema and revision advance from 4 to 5 and 3 to 4, which changes its
fingerprint. The Docs and Code presets reverse order as specified by the display order.
Their corresponding counts match.

Two early hosted attempts provided diagnostics only.
The stock headed Chrome attempt observed 34.1% trusted-input coverage in its first
control and refused the record.
The stock Chromium attempt returned without a profile file for every pair and side.
Neither inserted any browser ledger rows.
[First run](https://github.com/jlevy/metabrowser/actions/runs/45109522719) ·
[Chromium run](https://github.com/jlevy/metabrowser/actions/runs/45110293239)

## Matched HTTP Readiness

The [archived protocol](exp-102-protocol.txt) copies the matched-HTTP workflow
byte-for-byte from its commit before the run.
The earlier socket-ready and later optional-font series used their own workflow
revisions, linked in their sections.

Both installed wheels kept their original lockfiles.
The driver polled `/api/routes`, which reads the route list without loading the browser
shell or tree. It started a fresh Chrome profile immediately after the first HTTP 200
from each server. TCP-to-HTTP took 12–14 ms in the control and 1,228–1,267 ms in the
candidate.
The control browser reached navigation after 816–824 ms on four runs and after
9,972 ms on its first run.
That run remains in the ledger.
The candidate took 813–826 ms.
[Matched-readiness driver](https://github.com/jlevy/metabrowser/commit/0fd732be458f150bba7fb4a385b1d9711094d39b)

| Pair | Control first row, ms | Candidate first row, ms | Candidate / control | Control spawn to row, ms | Candidate spawn to row, ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 301 | 227 | 0.75 | 11,918 | 2,740 |
| 2 | 160 | 230 | 1.44 | 2,599 | 2,738 |
| 3 | 142 | 211 | 1.49 | 2,652 | 2,782 |
| 4 | 112 | 220 | 1.96 | 2,644 | 2,778 |
| 5 | 144 | 225 | 1.56 | 2,624 | 2,764 |

All ten captures were admitted.
The tab stayed visible.
Trusted-input coverage was 83.5–98.7% for the control and 97.7–97.9% for the candidate.
The candidate met all hard budgets in each run.
The first control alone exceeded a hard budget, with 7.1% main-thread blocking against a
5% budget. The stock comparator declined to judge the series across different locked
KPress environments.
The paired timings show the whole installed releases.

After HTTP readiness, median navigation TTFB was 17 ms on each build.
The latest startup-script response completed at a median of 134 ms on the control and
213 ms on the candidate.
Median `DOMContentLoaded` moved from 157 to 240 ms.
Both pages loaded 20 startup scripts, totaling 174 KB on the control and 220 KB on the
candidate. Rendering the first rows took 1–3 ms on the control and 3–4 ms on the
candidate.

The 1 KB `pending-tally-diagnostics.js` and the larger `tree-filter-model.js` each spent
40–41 ms between response start and end in every candidate capture, compared with 0–1 ms
in the control. For the smaller file the server reported 3.6–6.8 ms of work before
response start on the candidate and 4.9–18.8 ms on the control.
The later full-tree request also took longer, at 45–79 ms versus 3–18 ms.
Both versions draw the inline first rows before that full-tree request.

The 40 ms delay is consistent with delayed acknowledgments on a Linux TCP connection
with Nagle’s algorithm enabled.
The new CLI holds the listening socket, and its constructor leaves the protocol
implicit. Python’s accept path carries that protocol value into the accepted socket.
On Linux, asyncio enables `TCP_NODELAY` only when the Python socket reports TCP
explicitly. The earlier host/port binding path takes that protocol value from address
resolution. A focused change to declare TCP can distinguish this explanation from cold
asset reads and compression in a follow-up release comparison.
[Python socket accept](https://github.com/python/cpython/blob/v3.13.7/Lib/socket.py#L288-L302)
·
[asyncio TCP socket check](https://github.com/python/cpython/blob/v3.13.7/Lib/asyncio/base_events.py#L190-L199)

## Optional-Font Follow-Up

A separate run measured the same control against
`78e3cdb320a10151d4652076f3941be937284870`, the optional-font branch from
[sidebar font fix](https://github.com/jlevy/metabrowser/pull/731), using the same HTTP
readiness check and Chrome settings.
Its candidate wheel SHA-256 is
`c07352fbfa209a1da389acaa471e6b2fec9cee8989b23bc09e13abf47fdd0acf`. All four admitted
candidate captures passed every hard gate.
The first pair is incomplete.
The control’s trusted-input coverage was 53.9%. The candidate driver saved the raw
profile but exited with a temporary-profile cleanup error before the stock recorder
could attest the capture.
Neither capture entered the normalized ledger.

| Pair | Control first row, ms | Font candidate first row, ms | Candidate / control | Control spawn to row, ms | Candidate spawn to row, ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | 139 | 220 | 1.58 | 2,595 | 2,702 |
| 3 | 140 | 222 | 1.59 | 2,609 | 2,698 |
| 4 | 140 | 217 | 1.55 | 2,607 | 2,697 |
| 5 | 151 | 215 | 1.42 | 2,590 | 2,729 |

Every admitted pair exceeded the 1.3× first-row tolerance.
The two scripts again spent 40–42 ms from response start to end on the candidate and 0–2
ms on the control. The four-pair result reproduces the remaining delay.
A release comparison requires five admitted pairs.
[Optional-font run](https://github.com/jlevy/metabrowser/actions/runs/45113917455) ·
[Optional-font workflow](https://github.com/jlevy/metabrowser/commit/1d2df3b7f499961027bf47fedee4991c0db25e87)

## Linux TCP Follow-Up

The next wheel combined the narrowed sidebar font rule with an explicit TCP protocol on
the reserved listening socket.
Its commit was `ed7e1f10ffcd7be3524113edd6dc940cfe74c708` and its wheel SHA-256 was
`90ba47f82e5f52651f07f76ca834c68fcc07757cb215b79e9c465937192405e8`. The Linux transport
test verified the adopted listener’s accepted socket has `TCP_NODELAY` enabled, matching
the ordinary host/port bind.
All 25 focused socket tests passed on Linux and macOS. On the macOS 3.13.7 control,
Python did not expose `SO_PROTOCOL` and all three socket configurations had the same
accepted transport setting.

The 40–42 ms header-to-body interval fell to 0–1 ms on both monitored scripts, across
all five candidate captures.
The five candidate first rows took 124–140 ms and each cleared every hard browser
budget. Candidate trusted input covered 98.3–98.4% and the tab stayed visible for every
capture.
The backend first-row median stayed at 10 ms on both builds, ordered rows stayed
identical, and the raw tally verdict still reported the nine expected metadata and
preset-order differences.

| Pair | Control first row, ms | TCP candidate first row, ms | Candidate / control | Control spawn to row, ms | Candidate spawn to row, ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 3 | 163 | 133 | 0.82 | 2,647 | 2,664 |
| 4 | 130 | 124 | 0.95 | 2,554 | 2,634 |
| 5 | 131 | 140 | 1.07 | 2,555 | 2,634 |

The first control trace was refused for 32.1% trusted-input coverage.
The second control driver wrote a profile and then reported an `ENOTEMPTY` error
removing the browser’s temporary profile.
The two candidate captures paired with those controls passed their individual budgets
and remain in the ledger.
The relative comparison above uses the three complete pairs only.
[Combined font and TCP run](https://github.com/jlevy/metabrowser/actions/runs/45116045122)
· [TCP fix](https://github.com/jlevy/metabrowser/pull/733)

## Exact TCP Pull Request Head

The final comparison measured `80fb76d63b8d19c2e5537ea6e9c9128506b3ad63`, the TCP fix on
the merged sidebar font revision.
Its wheel SHA-256 was
`b3be120606fa26402b39950fe19e047b391501fa8f1800a0da4ffea1a1e838cd`. The workflow rebuilt
the control wheel from the `v0.12.0` tag and its lockfile.
The [preregistered replacement workflow](exp-102-exact-pr-head-protocol.txt) recorded
the same installed-wheel, synthetic-corpus, input, visibility, and hard-budget checks.
It specified five complete interleaved pairs and allowed at most three additional whole
pairs to replace a pair with a refused capture.
A bounded retry for removing the Chrome profile ran after trusted input stopped, the
profile was written, and Chrome exited.

| Pair | Control first row, ms | Candidate first row, ms | Candidate / control | Control spawn to row, ms | Candidate spawn to row, ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | 135 | 129 | 0.956 | 2,601 | 2,621 |
| 3 | 148 | 119 | 0.804 | 2,649 | 2,620 |
| 4 | 151 | 123 | 0.815 | 2,624 | 2,650 |
| 5 | 142 | 159 | 1.120 | 2,637 | 2,675 |
| 6 | 142 | 117 | 0.824 | 2,577 | 2,616 |

Pair 1’s control stayed visible, but its trusted input covered 72.6% of the measured
window, below the 80% admission gate.
Its raw first row was 151 ms and first contentful paint was 2,624 ms.
That raw trace and its refusal are retained in the run artifact.
Pair 6 made up the missed comparison.
The admitted candidate half of pair 1 also passed every hard budget and stays in the
ledger, outside the paired analysis.

All five complete pairs were visible.
Control input coverage ranged from 98.4% to 98.5%, and candidate coverage ranged from
98.3% to 98.4%. Every admitted capture cleared all hard budgets.
The paired candidate first-row median was 123 ms versus 142 ms for the control.
All five ratios were within the 1.3× rough-cut release tolerance.
Pair 5 alone exceeded the 1.1× careful tolerance, at 1.120×, while the other four
candidates were faster than their paired control.
The ranges overlap, and a single exceedance does not establish a repeatable wrong-way
result. The careful protocol would rerun pair 5 before a fine-grained claim.
Measured from process spawn, all five candidate times were within 1.6% of their matched
control.

Both builds delivered the two monitored script bodies within 0–1 ms after response start
in the complete pairs.
The Linux unit check again passed all 25 tests.
The backend first-row medians were 10 ms in both conditions.
Backend startup to an answered request was 1.608 s and 1.688 s at the median.
The ordered rows matched and the raw tally check again flagged the nine explained
registry and ordering differences.
The stock comparator again refused the unequal locked KPress environments.
The first-row ratios above describe whole installed releases from the admitted paired
captures. The run artifact keeps the comparator statuses, raw traces, capture manifest,
and per-capture hard-budget results.
[Exact PR-head benchmark](https://github.com/jlevy/metabrowser/actions/runs/45117924502)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
