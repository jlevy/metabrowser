---
type: is
id: is-01m6wdjwshpc22fta0bf5mwwbs
title: Preserve unfinished PR prefetch across catalog prefix updates
kind: bug
status: in_progress
priority: 1
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6th4qn5b1s27zkw8rw3736h
hold: null
hold_until: null
created_at: 2026-11-08T01:50:20.975Z
updated_at: 2026-11-08T09:53:45.877Z
started_at: 2026-11-08T09:53:45.590Z
---
A diagnostic ownership-fix smoke compared installed11db with source48be using independent catalog-only seeds and target310, eighteenth among29Open rows. The control had a core at initial classification; the candidate did not, and eight nearby Open rows remained deferred while later catalog cores accumulated. The candidate eventually warmed all314 cores and served the prepared target in77ms. This is not a matched speed comparison or proven regression. Reproduce with alternating trials and record initial prefix replacement, cancellation, provider attempts, lease deadlines and cursor scheduling. Test the hypothesis that a canceled priming cohort retains its attempt lease and deferred members wait behind the All traversal. Fix only if measurements/production-session evidence establish a useful change; preserve source/reader isolation, bounded attempts and fairness for later rows.

## Notes

Confirmed on unchanged main 9416b78b by a production-controller session and actual backend lease probes. A same-source/reader/epoch prefix revision releases the active accepted core producer, canceling unfinished work while correctly retained attempt leases defer unchanged early members. Retained-owner control completes them with one provider call. Implement the smallest client ownership correction; preserve backend leases, real ownership cancellation and later-row fairness. Evidence: b0aq-mechanism-20261108/diagnostic.json in the private release-preparation evidence. This establishes the mechanism, not painted latency or attribution of the historical smoke. Future Files source/branch workflow mb-itzy remains paused and excluded.
