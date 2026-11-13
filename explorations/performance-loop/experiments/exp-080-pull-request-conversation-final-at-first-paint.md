---
title: The Pull Request Conversation Final at First Paint
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-080
  title: The Pull Request Conversation Final at First Paint
  date: "2026-11-13"
  hypotheses:
    - H106
  subject:
    corpus: Standalone clone of this repository at 7a02fed4 with its own refs, clean; its commit, cleanliness, trunk, and refs did not move during the series.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 3
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the editable control checkout at 09903292, clean at the start and end of every run, one server process per run.
    candidate: metab 0.12.1.dev165+9903292 (+182 commits, 5a56f0a8f), the editable checkout of claude/perf-prpage at 5a56f0a8, clean at the start and end of every run, one server process per run. It carries H106's changes and H92's (exp-065), measured in one series.
    record: exp-065-transition-samples.jsonl
  results:
    - metric: Conversation transitions per run whose description showed before its final form
      control_median: 5
      candidate_median: 1
      control_range: [5, 7]
      candidate_range: [1, 1]
      overlapping: false
    - metric: description final minus shown, ms, pulls.pr_to_pr.revisit
      control_median: 16.7
      candidate_median: 0
      control_range: [16.7, 33.4]
      candidate_range: [0, 0]
      overlapping: false
    - metric: description final minus shown, ms, pulls.pr_to_pr.cold
      control_median: 16.7
      candidate_median: 0
      control_range: [16.7, 16.7]
      candidate_range: [0, 0]
      overlapping: false
    - metric: description final minus shown, ms, pulls.pr_to_pr.hover_click
      control_median: 33.2
      candidate_median: 0
      control_range: [16.8, 33.3]
      candidate_range: [0, 0]
      overlapping: false
    - metric: description final minus shown, ms, pulls.pr_changes_to_pr
      control_median: 16.7
      candidate_median: 0
      control_range: [16.7, 16.7]
      candidate_range: [0, 0]
      overlapping: false
    - metric: description final minus shown, ms, pulls.list_to_pr.cold
      control_median: 16.7
      candidate_median: 33.4
      control_range: [16.7, 33.4]
      candidate_range: [33.3, 49.9]
      overlapping: true
    - metric: body layout shift after painted ready per run, every Conversation transition
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      overlapping: true
    - metric: pr_description_final_ms.pulls.pr_to_pr.cold
      control_median: 63
      candidate_median: 61
      control_range: [62, 63]
      candidate_range: [61, 63]
      overlapping: true
    - metric: pr_description_final_ms.pulls.pr_to_pr.revisit
      control_median: 46
      candidate_median: 46
      control_range: [43, 63]
      candidate_range: [46, 46]
      overlapping: true
    - metric: pr_description_final_ms.pulls.pr_to_pr.hover_click
      control_median: 63.8
      candidate_median: 80.4
      control_range: [60.7, 64.1]
      candidate_range: [80.2, 81.5]
      overlapping: false
    - metric: pr_description_final_ms.pulls.pr_changes_to_pr
      control_median: 79.4
      candidate_median: 111.9
      control_range: [77.8, 79.5]
      candidate_range: [111.4, 112.7]
      overlapping: false
    - metric: pr_description_final_ms.pulls.list_to_pr.cold
      control_median: 74.7
      candidate_median: 90.6
      control_range: [72.5, 76.1]
      candidate_range: [90.4, 100.8]
      overlapping: false
    - metric: painted_ready_ms.pulls.pr_to_pr.revisit
      control_median: 28.8
      candidate_median: 46.0
      control_range: [26.5, 29.3]
      candidate_range: [45.8, 46.2]
      overlapping: false
  complexity:
    lines_changed: 2006
    new_dependencies: []
    new_failure_modes:
      - A conversation's first paint of a full record waits out of sight for the Markdown of the texts on its first screen, up to DESCRIPTION_HOLD_MS (200 ms); past it the texts show plain and their Markdown replaces them.
      - Rendered texts are kept for the session, bounded by count and characters (64 descriptions and 1,000,000 characters; 256 other parts and 2,000,000), so a revisit is final at once and the oldest are dropped.
      - Commits that arrive after the conversation has painted go after everything shown, so a first visit's order differs from a return's, which places them among the cards.
    notes: "Shared with exp-065 (one branch, one build). 1,715 lines added and 291 removed in product code (09903292..5a56f0a8), 1,173 and 242 of them in pull-page.js, where most of H106 lives, and pull-state.js (71); tests, goldens, and documentation are another 2,291 and 68."
  verdict:
    decision: accepted
    primary_metric: Conversation transitions per run whose description showed before its final form
    reason: "Decided on three valid back-to-back pairs of the pulls and maintabs journeys (six pairs excluded for load before any result was read). The named metric fell from 5 (5-7) to 1 (1-1) per run with separated ranges. The prediction's 0 was not observed: the 1 is pulls.list_to_pr.cold in every candidate run, a page installed straight into the pane, where the milestone's on-screen test, which ignores visibility, is inferred to read the held, hidden description. Body movement after first paint was 0 in both builds, so that half shows no effect in this regime. The guards moved the wrong way and are accounted for by the hold: the description reaches its final form at the same time as the control on the cold pull request switch and the revisit, and 16 to 33 ms later on three cold clicks, at 61 to 112 ms. H77's accepted range (1.27-1.56 s in exp-045) is seconds in a cold regime and is not given back. Judgment: worth it."
    commit: 5a56f0a8
---
**Status:** Accepted.
Measured in
[exp-065](exp-065-one-read-per-click-trees-that-open-once-and-a-held-changes-paint.md)’s
series: three valid interleaved pairs of the pulls and maintabs journeys on harness
revision 4 (`5031dc16`), six pairs excluded for load before any result was read.
Its protocol, identities, load table, and hold spans are there; this record reads the
Conversation’s metrics.

## Why This Round

H106 in the
[load-time plan](../../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md)
says a pull request’s description paints as plain text and is then replaced by Markdown,
and the full record and commit rows rebuild or insert into the painted Conversation.
Caching Markdown, patching in place, and placing commits once make the body final at
first paint. It revisits H77, accepted in exp-045, and the prepared descriptions of H81
and H84, and warns that a hold for Markdown in flight could give those gains back.
The bead is `mb-gsa0`; the pull request is #369.

## Protocol

Declared before the series, in exp-065’s protocol:

- **Metric 1, which decides.** Per run, the Conversation transitions (those declaring
  `prDescriptionShown`) whose description showed before its final form:
  `prDescriptionFinal` minus `prDescriptionShown` above 0, plain text replaced by
  Markdown after the first paint.
  Ten such transitions a run: eight of the pulls journey and two of maintabs.
  Predicted lower (candidate 0), judged on ranges.
- **Metric 2.** Per run, the body’s layout-shift sum after painted ready over the same
  transitions, and compare’s `preview_top_replaced` and `shift_sum_no_input` on pull
  request transitions: predicted not higher.
- **Guards.** `pr_description_final_ms` and `pr_description_shown_ms` on the cold
  Conversation clicks, and `painted_ready_ms` on every Conversation transition, by
  compare’s pair rule; H77’s exp-045 range (1.27–1.56 s, a cold core-only regime) is
  context, not a threshold.
- **Instrument.** The transition scenario.
  Metric 1 and the body shift are derived from its milestones and shift entries by
  `exp-065-instruments/derive-h92-h106.mjs`, in
  [exp-065-derived-samples.jsonl](exp-065-derived-samples.jsonl).

Regime notes, true of the candidate measured: the conversation’s first paint waits out
of sight for the Markdown of every text on its first screen, measured from the page’s
own top, with the next three texts asked for ahead; over the loading page, the loading
heading stays while the hold lasts, and the record’s header paints with the conversation
at release; a slow landing keeps the loading blocks that had shown, in place, until the
conversation shows.

## Results

### Metric 1: a description shown before its final form

| Run | Control: transitions, and final minus shown | Candidate |
| --- | --- | --- |
| Pair `06-59-22#1` | 7 of 10: `list_to_pr.cold` +16.7, `pr_to_pr.cold` +16.7, `pr_to_pr.revisit` +33.4, `pr_to_pr.hover_click` +16.8, `pr_changes_to_pr` +16.7, `main_subject.commits_to_pulls` +16.6, `main_subject.files_to_pulls` +16.6 | 1 of 10: `list_to_pr.cold` +33.3 |
| Pair `09-25-37#1` | 5 of 10: `list_to_pr.cold` +16.7, `pr_to_pr.cold` +16.7, `pr_to_pr.revisit` +16.7, `pr_to_pr.hover_click` +33.3, `pr_changes_to_pr` +16.7 | 1 of 10: `list_to_pr.cold` +49.9 |
| Pair `09-25-37#2` | 5 of 10: `list_to_pr.cold` +33.4, `pr_to_pr.cold` +16.7, `pr_to_pr.revisit` +16.7, `pr_to_pr.hover_click` +33.2, `pr_changes_to_pr` +16.7 | 1 of 10: `list_to_pr.cold` +33.4 |
| Per run | 5 (5–7) | 1 (1–1) |

**The candidate’s one remaining transition.** On `pulls.list_to_pr.cold`, the journey’s
first click, the candidate’s description “shows” at 57 (41–68) ms and is final at 91
(90–101) ms. Its painted ready, whose test requires visible useful content in the body,
is 90.6 (90.4–100.8) ms: no frame before the final one showed the body’s content.
That click opens a page with none on screen to retain, so the page is installed straight
into the pane and holds its body with `visibility: hidden`, and the milestones’
on-screen test reads only geometry.
The remaining 1 is inferred to be that test reading the hidden description during the
hold, not plain text the reader saw.
It is not proven here; if it were real, the first cold click of a document would still
show plain text for 33 to 50 ms.

### Metric 2: the body after first paint

| Reading | Control | Candidate |
| --- | --- | --- |
| Body shift after painted ready, every Conversation transition, per run | 0 (0–0) | 0 (0–0) |
| `shift_sum_no_input`, every pull request transition | 0 | 0 |
| `preview_top_replaced`, Conversation transitions | 0 to 5, by transition | the same, transition by transition |

The control moved nothing in the body after first paint in this regime: its
plain-to-Markdown replacements left no layout-shift entry with a body source, and no
commit row moved anything either.
Why the replacements shift nothing on these pull requests is not measured here.
That half of the hypothesis has no effect to show in this regime.

### Guards

| Transition | Description shown | Description final | Painted ready |
| --- | --- | --- | --- |
| `pulls.list_to_pr.cold` | 58.0 (39.1–59.4) → 57.0 (40.7–67.5), overlap | 74.7 (72.5–76.1) → 90.6 (90.4–100.8), 1 of 3 pairs beyond | 58.0 (39.1–59.4) → 90.6 (90.4–100.8), 1.70x, 3 of 3 |
| `pulls.pr_to_pr.cold` | 45.8 (45.6–46.3) → 61.4 (61.2–62.6), 1.34x, 3 of 3 | 63 (62–63) → 61 (61–63), no difference | 45.8 (45.6–46.3) → 61.4 (61.2–62.6), 1.34x, 3 of 3 |
| `pulls.pr_to_pr.revisit` | 28.8 (26.5–29.3) → 46.0 (45.8–46.2), 1.59x, 3 of 3 | 46 (43–63) → 46 (46–46), no difference | 28.8 (26.5–29.3) → 46.0 (45.8–46.2), 1.59x, 3 of 3 |
| `pulls.pr_to_pr.hover_click` | 30.9 (30.5–43.9) → 80.4 (80.2–81.5), 2.60x, 3 of 3 | 63.8 (60.7–64.1) → 80.4 (80.2–81.5), 1 of 3 beyond | 30.9 (30.5–43.9) → 80.4 (80.2–81.5), 2.60x, 3 of 3 |
| `pulls.pr_changes_to_pr` | 62.7 (61.1–62.8) → 111.9 (111.4–112.7), 1.80x, 3 of 3 | 79.4 (77.8–79.5) → 111.9 (111.4–112.7), 1.42x, 3 of 3 | 62.7 (61.1–62.8) → 111.9 (111.4–112.7), 1.80x, 3 of 3 |
| `pulls.tab.conversation_revisit` | 30 → 28 | 30 → 28 | 30.0 (29.8–30.0) → 28.3 (28.1–29.3), within the tolerance |
| `pulls.tab.conversation_revisit_2` | 30 → 28 | 30 → 28 | 29.9 (29.2–43.4) → 28.1 (27.7–28.5), one pair to rerun |
| `pulls.history_back` | 40 → 41 | 40 → 41 | 39.5 (36.9–42.7) → 41.4 (40.6–42.0), no difference |
| `main_subject.commits_to_pulls` | 65 → 65 | 65 → 65 | 64.9 (64.3–65.2) → 64.7 (64.5–81.8), no difference |
| `main_subject.files_to_pulls` | 65 → 65 | 65 → 65 | 64.7 (62.9–65.1) → 64.7 (64.6–65.3), no difference |

Shown and painted ready move later because the page now shows nothing of its body until
the body is final. What the reader waits for, the final description, arrives at the same
time on the cold switch and the revisit, one frame later on the first click and the
hover click, and two frames later on the switch from another pull request’s Changes, at
61 to 112 ms. The hold spans in exp-065 (first paint 25 to 151 ms, median 41.5, none at
the bound) are that wait.

H77’s accepted range is the cold, core-only description in exp-045, 1.27 to 1.56 s
against 3.06 to 4.09 s. This series is warm, and every final description here is 28 to
112 ms; nothing in it gives back seconds.

## Verdict

**Accepted.** The named metric fell from 5 (5–7) to 1 (1–1) per run with separated
ranges. The prediction’s 0 was not observed; the remaining 1 is the first cold click,
explained above as a reading of the hidden description, by inference.
Metric 2 did not move in either build.
The guards’ wrong-way results are the hold, which is this change: the page waits out of
sight until its body is final instead of showing plain text it then replaces.
**Complexity, a judgment:** the change keeps rendered texts across pages, reconciles the
body by content, and holds the first paint, in about 1,200 lines of `pull-page.js`. It
removes every visible plain-to-Markdown replacement the scenario saw, at a cost of zero
to two frames to the final description.
Worth it, for the owner’s requirement that nothing flashes as a page loads.

Instruments: the transition scenario for every figure here; the derivation for metric 1
and the body shift; the hold spans are exp-065’s.

## Changes After the Measured Candidate

These came after `5a56f0a8` and are off the paths this round measured, so they were not
measured again:

- `62ebfd75` (review E1, E2): a page that goes while its Changes hold waits keeps the
  diff out of sight and records the wait as `cancelled`; the tab keys’ wait under a held
  first paint is stated and tested.
  The series never cancels a page during a hold.

## Limits

- Three valid pairs, on a loaded machine; see exp-065’s load table and Limits.
- The milestones’ on-screen test reads geometry, not visibility, so a held description
  on a page installed straight into the pane can count as shown; the deciding metric’s
  remaining 1 rests on that inference.
- The corpus’s pull requests have few comments on their first screens, so the hold
  waited for the description alone in every span measured; a conversation whose first
  screen shows several texts waits a round trip per two texts.
- Headless Chrome only.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
