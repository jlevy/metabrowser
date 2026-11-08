---
type: is
id: is-01m6wdjwshpc22fta0bf5mwwbs
title: Investigate delayed early PR cores during catalog replacement
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6th4qn5b1s27zkw8rw3736h
created_at: 2026-11-08T01:50:20.975Z
updated_at: 2026-11-08T01:50:20.975Z
---
A diagnostic ownership-fix smoke compared installed11db with source48be using independent catalog-only seeds and target310, eighteenth among29Open rows. The control had a core at initial classification; the candidate did not, and eight nearby Open rows remained deferred while later catalog cores accumulated. The candidate eventually warmed all314 cores and served the prepared target in77ms. This is not a matched speed comparison or proven regression. Reproduce with alternating trials and record initial prefix replacement, cancellation, provider attempts, lease deadlines and cursor scheduling. Test the hypothesis that a canceled priming cohort retains its attempt lease and deferred members wait behind the All traversal. Fix only if measurements/production-session evidence establish a useful change; preserve source/reader isolation, bounded attempts and fairness for later rows.
