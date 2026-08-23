---
title: The skeleton stops growing under the reader
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-009
  title: The skeleton stops growing under the reader
  date: "2026-08-22"
  hypotheses:
    - H50
  subject:
    corpus: build_project_corpus at 10 projects (246,282 files, 31,161 directories)
    corpus_files: 246282
    corpus_dirs: 31161
    host_system: Darwin 25.5.0
    browser: Chromium
    viewport: "1280x900"
    cold: true
  method:
    runs_per_condition: 1
    interleaved: true
    control: the filter bar and the tally row are rendered before they have content, and grow when it arrives
    candidate: both reserve a line box of the type they hold, derived rather than measured
    record: explorations/performance-loop/results/runs.jsonl
  results:
    - metric: filter_bar_shift_px
      control_median: 24
      candidate_median: 0
      control_range: [24, 24]
      candidate_range: [0, 0]
      change_pct: -100.0
      overlapping: false
    - metric: summary_shift_px
      control_median: 43
      candidate_median: 23
      control_range: [43, 43]
      candidate_range: [23, 23]
      change_pct: -46.5
      overlapping: false
    - metric: total_downward_shift_px
      control_median: 67
      candidate_median: 23
      control_range: [67, 67]
      candidate_range: [23, 23]
      change_pct: -65.7
      overlapping: false
    - metric: tree_region_repaints
      control_median: 4
      candidate_median: 4
      control_range: [4, 4]
      candidate_range: [4, 4]
      change_pct: 0.0
      overlapping: true
  complexity:
    lines_changed: 34
    new_dependencies: []
    new_failure_modes:
      - "Both reservations are floors, and the tally row now exceeds its floor: main's split row wraps to a second line in a 300 px pane, so 23 px of the original 67 remain. A one-line reservation cannot cover a row whose settled height depends on its own content."
    notes: One design token, two min-height declarations, one changed argument in the inline render, and a guard so a no-op does not record a repaint.
  verdict:
    decision: accepted
    primary_metric: total_downward_shift_px
    reason: "67 px of downward movement on every load and every reload, now 23, measured directly at 1280x900. The filter bar is fixed outright: 13 px standing, 37 populated, now 37 throughout. The tally row is half fixed -- its reservation holds one line, and main's split row wraps to two in a 300 px pane, so it still grows 33 px to 56. Registered as H54 rather than papered over with a two-line reservation, which would leave dead space whenever the row does not wrap. Repaint count is unchanged, which is the honest reading: this round stopped most of the movement, it did not stop the page being assembled in front of the reader."
---
# The skeleton stops growing under the reader

## Why this round exists

Every metric this loop had measured answers *when the data arrived*. None answered *what
the reader saw, and whether it stayed put*. The probe recorded 28 numbers and not one
was a paint or a layout measure; `fcp_ms` existed and came back non-null in one run out
of eight.

So the question — does the page render its structure at once and fill it in, or does it
assemble itself visibly?
— had never been asked.

## What the server actually ships

Read off the wire rather than off the live DOM:

| region | in the HTML |
| --- | --- |
| `#nav-filter-bar` | **empty** — `<div id="nav-filter-bar"></div>` |
| `#tab-files` | `"Loading files…"` |
| `#preview-pane` | `"Select a file to preview."` |
| `#index-progress` | `"Scanning…"` |

Not a skeleton: three text placeholders and one empty element, each replaced wholesale
later.

## What was measured, and what could not be

**Two of the obvious metrics are unavailable in this environment, and saying so is part
of the result.** Chromium does not compute largest-contentful-paint for a page that has
never been visible, and the pane reports `visibilityState: "hidden"` permanently — a
clean load returned `lcp: null` with zero candidates.
Cumulative layout shift is recorded, but it needs real layout to mean anything, and the
pane silently resets to 0×0 on every navigation.
An early reading of `cls: 0` was taken in a collapsed pane and was worth nothing:
nothing can shift when nothing has height.

So the shift was measured directly instead, which needs neither visibility nor a
particular viewport: clone a region stripped of its content, read its height, and
compare with the populated one.
That is the jump a reader gets, in pixels, and it is reproducible here.

|  | control | candidate |
| --- | ---: | ---: |
| `filter_bar_shift_px` | 24 | **0** |
| `summary_shift_px` | 43 | **23** |
| `total_downward_shift_px` | 67 | **23** |
| `tree_region_repaints` | 4 | 4 |

Both conditions are the same server, the same corpus, and the same pane: the control is
this build with the two `min-height` declarations deleted, which the probe confirms by
reading back `min-height: auto` off the served stylesheet before it measures anything.

The measurement now lives in `probe.js` and the four figures are in the standing metric
list, so `compare` prints them for every future round.
They were hand-measured and hand-pasted the first time this round was written, which
made them a claim rather than a record — and made them impossible to re-check without
repeating the hand work.
Re-checking is exactly what turned out to be needed.

## The two causes

**The filter bar is shipped empty and filled by JavaScript.** With `padding: 6px` and a
1 px border and nothing inside, it stands 13 px tall; once `filter_controls.js` puts a
row of chips in it, 37 px.
The entire tree below it moves down 24 px, every load.

**The tally row paints before it has numbers.** This one is self-inflicted:
[exp-004](exp-004-the-shell-carries-the-first-rows.md) began painting rows from the
inlined payload, and passed `chromeHtml: ""` because that payload carries no counts.
So the rows landed with no tally row above them, and gained one when the fetch returned.
Before that experiment there were no rows in place to push, so the jump did not exist.

Both fixes reserve a line box of the type inside, derived rather than measured off one
instance: a new `--chip-height` token, and the same 1.5 line-box arithmetic for the
tally row. Derived because the shell offers the reader a choice of font sets, and a
hardcoded pixel height would drift the first time one changed — which is not a
hypothetical, as the next section shows.

## What the rebase changed, and why this round was measured twice

This round was first measured on a branch whose base was later rewritten.
Rebasing it onto `main` picked up two changes to the very row under measurement: the
tally row’s type moved to `--nav-font-size` (13 px), and the row itself became a *split*
row that reports tracked and ignored files separately.

That second change is what matters.
The settled row is no longer one line of text — at this corpus it reads
`20,640 files (248.7 MB) +90,030 ignored (1430.1 MB)`, and in a 300 px navigation pane
it wraps to two, standing 56 px rather than 33.

So the round was re-measured rather than re-stated, and the honest numbers are worse
than the first ones: 67 px of control movement instead of 42, and 23 px left instead of
zero.
The derived reservation did its job — it computes to 33 px, exactly the height of a
split row that fits on one line — and the derivation is the reason it needed no edit
when the font token changed underneath it.
What it cannot do is reserve a height that depends on the row’s own content.

Reserving two lines unconditionally would take the number to zero and is the wrong
trade: the row does fit on one line in a wider pane, and every reader with one would get
23 px of permanent dead space above their tree in exchange for a jump they never saw.
That is
[H54](../../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#hypotheses),
and it wants the pending row to be shaped like the settled one rather than a taller
floor.

## What this round did not do

**Repaint count is unchanged.** The page moves less, and it is still assembled in
several passes over the tree region: the inlined rows, the fetched rows, and a refresh.
Stopping the movement is not the same as stopping the assembly, and the second is
[H11](../../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#hypotheses)
— patch the panel rather than replacing it wholesale.
The figure here is 4 rather than the 3 seen on a cold load, because these runs were
taken against a settled index, which adds the summary refresh pass.
It is the same in both conditions, which is all this round asks of it.

**23 px of the movement is still there**, in the tally row, and the next section says
why it is being registered rather than smothered.

One measurement artifact was also fixed rather than measured around: the inline render
recorded a `renderTreeNodes:inline` span even on the visit where it declined to paint,
so the repaint count read 5 where three paints had happened.
Now the span is recorded only when it paints.
That mattered because repaint count is a metric as of this round.

## Limitations

One corpus, one viewport, n=1 per condition — enough for a 67-px-to-23 effect and
nothing subtler. The reservations are *floors*, and the first version of this write-up
named exactly the case that then happened: “a tally row carrying more than one line
still grows past them.”
It does.

The measurement is of two named regions, not of the page: a region that grows and was
not measured would not appear here.
Both figures are also pane-width dependent, because wrapping is — the 23 px is what a
300 px navigation pane gives, and a wider one gives zero.
And `lcp_ms` and `cls` are recorded but null, so the metric a browser would report is
still unknown — that needs a visible window and is H51.

## Verdict

**ACCEPTED on `total_downward_shift_px`,** 67 px → 23, for one token and two
declarations. The filter bar is finished; the tally row is not, and the remainder is
[H54](../../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#hypotheses).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
