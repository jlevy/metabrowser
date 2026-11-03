---
title: PR Files Start from a Prepared Manifest and a Visible Patch Prefix
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-041
  title: PR Files Start from a Prepared Manifest and a Visible Patch Prefix
  date: '2026-11-03'
  hypotheses:
  - H49
  - H58
  - H73
  subject:
    corpus: 'Cached immutable public PR comparisons: astral-sh/ruff#29817 (1031 files), #29121
      (1627), #29869 (39), and python/typeshed#15711 (650). Identical Git objects and endpoint
      records for both builds.'
    corpus_files: 1627
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0; CPython 3.14.7; Git 2.50.1; Node 24.18.0
    browser: Visible Google Chrome 152.0.7977.83, CDP-driven, fresh profile per run. document.visibilityState=visible;
      document.hasFocus=false was retained in every sample.
    viewport: 1400x900
    cold: true
  method:
    runs_per_condition: 3
    interleaved: true
    control: Installed wheel 0.11.1.dev822+9b624b3a, source 9b624b3aafa824b2837e7b26ace10c525a0f0688.
    candidate: 'Installed wheel 0.11.1.dev833+f5b8eec2, source f5b8eec2f5a8f856301121cc9acbc11141e3112d;
      includes the forward merge of #280 at 64fa6b1f.'
    record: exp-041-pr-rendering-samples.jsonl contains 24 cold, 12 mixed interaction, and 10
      corrected held-key samples. pr-page.mjs and pr-cdp.mjs preserve the recorder with an external-root
      parameter. A fresh server and browser do not mean cold filesystem or Git caches. No comparison
      warm-up GET was made; the candidate manifest was prepared separately as at fetch.
  results:
  - metric: first_text_ms_pr_29817
    control_median: 857.6
    candidate_median: 491
    control_range:
    - 816.8
    - 893.6
    candidate_range:
    - 470.6
    - 557.4
    overlapping: false
  - metric: first_viewport_filled_ms_pr_29817
    control_median: 867.1
    candidate_median: 497.6
    control_range:
    - 822.7
    - 899.5
    candidate_range:
    - 476.3
    - 574.1
    overlapping: false
  - metric: longest_load_task_ms_pr_29817
    control_median: 125
    candidate_median: 126
    control_range:
    - 122
    - 128
    candidate_range:
    - 125
    - 139
    overlapping: true
  - metric: first_text_ms_pr_29121
    control_median: 1350
    candidate_median: 518.9
    control_range:
    - 1348.7
    - 1354
    candidate_range:
    - 514.8
    - 559.5
    overlapping: false
  - metric: first_viewport_filled_ms_pr_29121
    control_median: 1373.7
    candidate_median: 530.2
    control_range:
    - 1373.7
    - 1381.8
    candidate_range:
    - 525.8
    - 570.3
    overlapping: false
  - metric: longest_load_task_ms_pr_29121
    control_median: 169
    candidate_median: 158
    control_range:
    - 165
    - 171
    candidate_range:
    - 157
    - 161
    overlapping: false
  - metric: first_text_ms_pr_15711
    control_median: 426.5
    candidate_median: 383.7
    control_range:
    - 425.6
    - 594.1
    candidate_range:
    - 377.1
    - 417.4
    overlapping: false
  - metric: first_viewport_filled_ms_pr_15711
    control_median: 433
    candidate_median: 389.8
    control_range:
    - 431.9
    - 615.1
    candidate_range:
    - 383.7
    - 423.4
    overlapping: false
  - metric: longest_load_task_ms_pr_15711
    control_median: 62
    candidate_median: 63
    control_range:
    - 61
    - 67
    candidate_range:
    - 62
    - 64
    overlapping: true
  - metric: first_text_ms_pr_29869
    control_median: 351.7
    candidate_median: 280.4
    control_range:
    - 346.7
    - 396.5
    candidate_range:
    - 278.9
    - 298.9
    overlapping: false
  - metric: first_viewport_filled_ms_pr_29869
    control_median: 356.8
    candidate_median: 286.2
    control_range:
    - 351.7
    - 401.1
    candidate_range:
    - 283.8
    - 305
    overlapping: false
  - metric: longest_load_task_ms_pr_29869
    control_median: 0
    candidate_median: 0
    control_range:
    - 0
    - 0
    candidate_range:
    - 0
    - 0
    overlapping: true
  - metric: actual_rows_after_keyup_ms_pr_29817
    control_median: 107.6
    candidate_median: 98
    control_range:
    - 100.6
    - 123.7
    candidate_range:
    - 96.1
    - 132.2
    overlapping: true
  - metric: actual_rows_after_keyup_ms_pr_29121
    control_median: 127.5
    candidate_median: 140.7
    control_range:
    - 124.7
    - 128.1
    candidate_range:
    - 136.9
    - 141.8
    overlapping: false
  complexity:
    new_dependencies: []
    notes: GitHub owns the bounded persisted-manifest bank; diff core accepts an explicit location
      and optional loader. PR hydration starts with 8 ready files, generic comparison retains
      50; all entries remain discoverable and on-demand hydration completes to the same document.
  verdict:
    decision: accepted
    primary_metric: first_text_ms_pr_29121
    reason: Cold first-text and full-viewport ranges improve in all four paired cases. Every file
      bar remains mounted and no final load task exceeds 161 ms. Jumps retain zero drift and remain
      below 50 ms for the header. The 500 ms cold goal is not met in every sample. The larger
      held-key actual-row median regresses about 13 ms, while remaining below the existing 150
      ms rows budget; no claim is made that every navigation is faster.
    commit: f5b8eec2f5a8f856301121cc9acbc11141e3112d
---
# exp-041: PR Files Start from a Prepared Manifest and a Visible Patch Prefix

The scoped improvement is accepted.
A prepared manifest and eight initial ready files reduce cold first text without
removing file headers or content.
The 500 ms cold goal remains open for some samples, and the larger held-key case has a
measured tradeoff.

## Conditions and Definitions

This is the public-PR counterpart of
[exp-040](exp-040-files-changed-recomputes-the-whole-patch-per-request.md), using its
custom PR recorder rather than the folder-row ledger.
The installed wheels share the same copied public Git objects and PR records.
Candidate manifests were prepared before navigation, as the fetch path now does.
Both builds start a fresh server and visible Chrome profile for each run; filesystem and
OS caches remain warm.
The copied record freshness timestamps were held identically in the future to suppress
background network refresh.
This measures opening a fetched PR, not cloning or fetching it.

Root and checkout agents paused heavy jobs during the timed windows, but host load was
not low: the one-minute load average ranged from 11.32 to 23.54. These are interleaved
local measurements under load, not idle-machine guarantees.
The browser was visible; its false focus flag is preserved.
Trusted keyboard events were verified with event.isTrusted.
There is no new github.com network comparison in this round.

First text is the second animation frame after a diff row appears.
The first-screen snapshot reads geometry once at that point.
Viewport completion uses native IntersectionObserver membership and DOM-only checks for
drawn rows versus reserved undrawn bodies; it marks a second animation frame after
visible reservations are filled.
It does not scan layout on every mutation.
All file bars are counted separately so an early row cannot hide unfinished header
mounting. The recorder waits at least 600 ms after the last observed load task before
collecting diagnostics.

## Cold Results

All values are median [minimum, maximum] milliseconds, n=3 per build and PR.

| Files | First Text: Baseline | First Text: Candidate | Full Viewport: Candidate | Longest Load Task: Baseline | Longest Load Task: Candidate |
| --- | --- | --- | --- | --- | --- |
| 1,031 | 857.6 [816.8, 893.6] | 491 [470.6, 557.4] | 497.6 [476.3, 574.1] | 125 [122, 128] | 126 [125, 139] |
| 1,627 | 1350 [1348.7, 1354] | 518.9 [514.8, 559.5] | 530.2 [525.8, 570.3] | 169 [165, 171] | 158 [157, 161] |
| 650 | 426.5 [425.6, 594.1] | 383.7 [377.1, 417.4] | 389.8 [383.7, 423.4] | 62 [61, 67] | 63 [62, 64] |
| 39 | 351.7 [346.7, 396.5] | 280.4 [278.9, 298.9] | 286.2 [283.8, 305] | 0 [0, 0] | 0 [0, 0] |

Every candidate sample reports all expected file bars, a fully drawn initial viewport,
zero reserved waiting files in its first-screen snapshot, and zero page exceptions.
A recorded longest task of zero means no task crossed the browser Long Tasks threshold
of 50 ms, not that no work ran.

The 1,031-file load-task median is 126 ms against 125 ms; its peak is 139 against 128
ms, on overlapping ranges.
Total blocking time is 90 [88, 119] against 94 [90, 100] ms.
The 1,627-file task median is 158 against 169 ms.
These results support the 200 ms load-task budget, not a blanket claim that every
main-thread measure improves.
The shorter wait also concentrates similar rendering work into a shorter loading
interval; no blocked-percentage improvement is claimed.

## Navigation and Held Keys

Three paired runs per large PR jump to file 7, the middle file, a file at 30 percent,
and the last file. Each jump follows its header position for one second.
The 1,031-file sessions also return with browser Back and click the Files tab with
trusted pointer input after Conversation prefetch settles.

| Case | Baseline | Candidate |
| --- | --- | --- |
| Back to First Text (ms, 1,031 files) | 193 [190, 202] | 181 [180, 184] |
| Prefetched Click to First Text (ms, 1,031 files) | 205 [196, 219] | 190 [187, 213] |
| Jump Header (ms), 1,031 files (12 jumps/build) | 20.5 [14.1, 38.8] | 18.5 [10.7, 31.6] |
| Jump Rows (ms), 1,031 files (12 jumps/build) | 73.3 [40.8, 183.8] | 65.6 [35.9, 86] |
| Actual Rows after Keyup (ms), 1,031 files | 107.6 [100.6, 123.7] | 98 [96.1, 132.2] |
| Jump Header (ms), 1,627 files (12 jumps/build) | 15.3 [10.9, 18.8] | 18.6 [11, 32.4] |
| Jump Rows (ms), 1,627 files (12 jumps/build) | 61.4 [45.5, 84.3] | 58.6 [48.8, 90.1] |
| Actual Rows after Keyup (ms), 1,627 files | 127.5 [124.7, 128.1] | 140.7 [136.9, 141.8] |

Every measured jump has zero drift.
No jump or held-key run records a task over 50 ms.
All 90 keydown events per hold are trusted, at a requested 33 ms interval; candidate
event-delay p95 is at most 0.9 ms in the corrected samples.
The scheduler starts one request during the hold, with at most one in flight at keyup;
three requests after settle include the final file and neighboring viewport work.

The existing scheduler distinguishes a 50 ms header/input goal from a 150 ms resting-row
goal. The corrected 1,627-file row median is 140.7 against 127.5 ms, on disjoint ranges.
This approximately 13 ms regression is retained; it stays below 150 ms and buys no
claimed interaction speedup.
Back and click ranges overlap or nearly meet, so their small differences are not a
general speed claim.
Ready file 7 also triggers neighboring deferred-file loads at the eight-file boundary;
the baseline initially held fifty files.

## Rejected Instrument and Work Moved to Fetch

An exploratory one-versus-eight probe read every section’s bounds on each mutation.
It raised apparent mount tasks above 200 ms through its own forced layout and is
excluded from the performance verdict.
Its qualitative screen observation was useful: one initial file left a second visible
file waiting on the 1,031-file case, while eight filled the initial viewport.
The final native-observer samples independently verify the eight-file viewport.

The inherited held-key field also accepted an availability message as text.
The raw mixed samples retain that field with a caveat; only
recorder_revision=actual-rows-v2 enters the actual-row table.
Corrected samples wait for .diff-line-text or .diff-split-row and two frames.
This avoids counting a loading status as rendered text.

The manifest work is moved to fetch, not eliminated.
One unpaired preparation under concurrent host work took 897 ms (1,031 files), 1,093 ms
(1,627), 438 ms (650), and 125 ms (39); these are observed costs, not controlled speed
comparisons. The four serialized manifests occupy approximately 1.73 MB per build; the
two-store bank held 3.47 MB including earlier-build slots.
Each store has 16 direct-mapped bounded slots: collisions safely evict, with no claim of
LRU retention. A GET still resolves and validates the source and reads the validated
cached manifest, but the cache-hit tests forbid recomputing it.

## Scope and Correctness

The GitHub route requests eight ready files; the generic folder/commit service retains
fifty. Initial-policy count participates in response identity and ETag, while manifest
identity stays shared.
Tests exercise both policies in one process, rejection of a wrong-policy validator,
complete hydration to byte-identical canonical document JSON, binary-only and empty
comparisons, and a first ready file that is too large followed by visible valid text.
No new large-file limit or content omission is introduced.

The collapsed-reservation and layout-switch review regressions are covered by the
production diff session: a collapsed held or deferred body has no reserved height,
reopening restores it, and manual or observer-driven layout switches recalculate undrawn
reservations. The current-file handle uses the same indexed file bars and bounded lookup
rather than scanning every file on each scroll.

## Reusing the Recorder

The [portable recorder](../pr-page.mjs) and [CDP helper](../pr-cdp.mjs) use Node
built-ins. Set PR_PERF_ROOT to a verified writable external task directory containing
public-cache, cfg, baseline-venv/bin/metab, and candidate-venv/bin/metab, with the
intended locked wheels installed.
Prepare candidate manifests at fetch, hold identical immutable records for both builds,
and use a fresh profile/process for every invocation.
For example:

```shell
node explorations/performance-loop/pr-page.mjs --build new \
  --pr https://github.com/astral-sh/ruff/pull/29817 --number 29817 --files 1031 \
  --scenario full --label candidate-1 --out "$PR_PERF_ROOT/result.jsonl"
```

Use scenario load for the cold comparison, full for Back/click/jumps, jumps for the
second large case, and hold for the corrected isolated key-release probe.
Alternate build order across at least three rounds.
Keep the full [recorded samples](exp-041-pr-rendering-samples.jsonl), including host
load, false focus, cache status, request counts, and the legacy-metric caveat.
The archived recorder has its task root parameterized and its unused helper removed; its
measurement logic is preserved.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
