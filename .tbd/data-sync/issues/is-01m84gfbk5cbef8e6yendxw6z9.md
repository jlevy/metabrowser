---
type: is
id: is-01m84gfbk5cbef8e6yendxw6z9
title: "Folder origin store: the retry timer starts a second acquisition right after a page's ask started and ended the due one"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels:
  - ci
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T15:30:28.067Z
updated_at: 2026-11-23T15:30:47.491Z
started_at: 2026-11-23T15:30:47.465Z
---
main red since b68cc9571: tests/test_checkout_store.py::test_a_failing_acquisition_is_tried_again_less_often_each_time saw waits [0.2005, 0.00033, 0.8008, 0.8011] (unit 3.13 1/2 in run 45187239621; admitted-git 2.56.1 in run 45197627733). Mechanism: CheckoutStore._keep_fresh computes when the next unasked try is due before it waits, and on TimeoutError called request_acquisition() without reading that again. A visible page's POST /api/source/refresh {for: page} starts the due try as soon as it is due; a try that fails at once ends in one task step, before the timer's TimeoutError handler runs in the same or next loop turn. The coordinator then reports nothing running, so the timer started a second try with no wait, and the failure count went up by two. Fix: the timer reads whether a try is due when its wait ends (_unasked_try_due), and a regression test holds the loop past the due time so the page's ask and the timer fall due in one turn.
