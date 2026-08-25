---
title: Git Revisions Swap Without Blanking
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-018
  title: Git revisions swap without blanking
  date: "2026-08-25"
  hypotheses: [H64]
  subject:
    corpus: fixed detached Metabrowser repository at 4c995e2
    corpus_files: 639
    corpus_dirs: 83
    host_system: Darwin 25.5.0
    browser: headed Chrome driven through the DevTools Protocol
    viewport: "1600x900"
    cold: false
  method:
    runs_per_condition: 3
    interleaved: true
    control: exact product at 4c995e2
    candidate: exact product at 00265ed
    record: three visible git-revisions scenarios per product against one detached corpus
  results:
    - metric: cold_first_transition_ms
      control_median: 225.2
      candidate_median: 214.2
      control_range: [219.0, 230.1]
      candidate_range: [204.7, 225.2]
      change_pct: -4.9
      overlapping: true
    - metric: cold_second_transition_ms
      control_median: 444.8
      candidate_median: 383.3
      control_range: [419.5, 476.8]
      candidate_range: [383.1, 425.4]
      change_pct: -13.8
      overlapping: true
    - metric: pointer_prepared_transition_ms
      control_median: 209.7
      candidate_median: 104.4
      control_range: [205.8, 245.0]
      candidate_range: [99.6, 109.2]
      change_pct: -50.2
      overlapping: false
    - metric: blank_frames_per_scenario
      control_median: 4
      candidate_median: 0
      control_range: [4, 5]
      candidate_range: [0, 0]
      change_pct: -100.0
      overlapping: false
    - metric: long_task_max_ms
      control_median: 148
      candidate_median: 132
      control_range: [146, 177]
      candidate_range: [126, 134]
      change_pct: -10.8
      overlapping: false
    - metric: animation_frame_max_ms
      control_median: 172
      candidate_median: 161
      control_range: [166, 197]
      candidate_range: [151, 176]
      change_pct: -6.4
      overlapping: true
    - metric: interaction_max_ms
      control_median: 56
      candidate_median: 72
      control_range: [56, 64]
      candidate_range: [64, 80]
      change_pct: 28.6
      overlapping: true
    - metric: retained_heap_mb
      control_median: 7.0
      candidate_median: 7.0
      control_range: [7.0, 7.1]
      candidate_range: [7.0, 7.1]
      change_pct: 0.0
      overlapping: true
  complexity:
    new_dependencies: []
    new_failure_modes:
      - stale speculative work could replace a newer selected revision
      - a staged diff could retain an extra mounted renderer after handoff
    notes: >-
      The candidate keeps the prior commit visible until a detached replacement is
      ready, overlaps commit-detail, diff-asset, and comparison work, and retains at
      most one pointer- or focus-prepared comparison. Every candidate run records one
      mounted comparison, zero page exceptions, and unchanged retained heap.
  verdict:
    decision: accepted
    primary_metric: blank frames and pointer-prepared transition time
    reason: >-
      Candidate transitions record zero blank frames in all three scenarios. The
      prepared transition falls from a 209.7 ms median to 104.4 ms with nonoverlapping
      ranges, while cold-transition ranges overlap and therefore support no speed
      claim. Maximum Long Task improves without overlap, retained heap is unchanged,
      and every run finishes with one mounted diff and no page exception.
    commit: 00265ed
---
# Git Revisions Swap Without Blanking

## Question

Can revision navigation keep the current commit continuously visible while preparing the
next comparison, and can one bounded intent prefetch remove useful work from the click
path?

Yes. The candidate records no blank frame in any run, and a pointer-prepared revision
becomes ready in about half the control time.
Cold-transition ranges overlap, so this experiment makes no general cold-speed claim.

## Fixed Product and Corpus

The comparison freezes the product and the browsed repository independently.
The control product is commit `4c995e2`; the candidate product is commit `00265ed`. Both
serve one detached Metabrowser corpus at `4c995e2`, so candidate documentation and
runtime commits do not change which history rows or comparisons are measured.

The runner alternates products and captures three visible, headed-Chrome scenarios for
each. Every scenario selects the same three revisions with browser-trusted input: two
cold rows and one row after a 450 ms pointer-intent interval.
Readiness is the first double-animation-frame boundary after the exact selected revision
and its comparison are mounted.
A frame monitor records whether the previous or next commit remains visible throughout
the handoff.

## Result

| Measure | Control median (range) | Candidate median (range) | Result |
| --- | ---: | ---: | --- |
| first cold transition | 225.2 ms (219.0–230.1) | 214.2 ms (204.7–225.2) | no detected difference |
| second cold transition | 444.8 ms (419.5–476.8) | 383.3 ms (383.1–425.4) | no detected difference |
| pointer-prepared transition | 209.7 ms (205.8–245.0) | 104.4 ms (99.6–109.2) | 105.3 ms faster |
| blank frames per scenario | 4 (4–5) | 0 | eliminated |
| maximum Long Task | 148 ms (146–177) | 132 ms (126–134) | lower |
| maximum animation frame | 172 ms (166–197) | 161 ms (151–176) | no detected difference |
| maximum Event Timing interaction | 56 ms (56–64) | 72 ms (64–80) | no detected difference |
| retained heap after GC | 7.0 MB (7.0–7.1) | 7.0 MB (7.0–7.1) | unchanged |

Every candidate scenario ends with one mounted diff, the exact last selected revision,
and zero page exceptions.
The interaction ranges touch at 64 ms and remain below the 200 ms hard gate.
The candidate’s higher median is retained as a caveat.
Event Timing can reward the control’s prompt spinner paint even though the useful commit
disappears; continuous content and exact ready-state timing therefore remain the primary
measures for this interaction.

## Attribution

Cold comparison requests spend most of their network duration in server work.
The first candidate comparison records 90–106 ms of server work for a 13,665-byte
response; the heavier second records 173–213 ms for 72,817 bytes.
Candidate diff mounting is a separate client cost, reaching 153–168 ms across the three
runs. Commit markup stays at 0.1 ms or less and diff-asset readiness at 0.3 ms or less.

Concurrency can overlap the server and mount paths, but host variation leaves both cold
transition ranges overlapping.
Pointer preparation is decisive: the candidate completes the detail and comparison
requests before the click, issues no click-time fetch, and records a 99.6–109.2 ms
handoff. The control still requests the comparison after the click and spends 98.6–120.7
ms on that request alone.

The bounded policy matters.
A direct sample of the newest 12 comparison documents totaled about 1.45 MB, with
individual responses from 2,457 to 438,612 bytes.
Preparing every visible history row would trade a visible pause for substantial
low-confidence server and memory work.
The accepted design retains one replaceable intent slot and aborts stale work where the
transport allows it.

## Decision

Accept atomic staging and one-slot pointer or focus preparation.
Reject decorative loading animation, all-visible-row prefetch, and a new server cache in
this round. Atomic staging fixes the visible discontinuity independently of latency.
The prepared path earns its cost with a nonoverlapping improvement, while the
measurements identify server comparison work and diff mounting as separate candidates
for future rounds.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
