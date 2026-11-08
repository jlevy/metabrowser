---
type: is
id: is-01m6wdjwshpc22fta0bf5mwwbs
title: Preserve unfinished PR prefetch across catalog prefix updates
kind: bug
status: in_progress
priority: 1
version: 4
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6th4qn5b1s27zkw8rw3736h
hold: null
hold_until: null
created_at: 2026-11-08T01:50:20.975Z
updated_at: 2026-11-08T10:07:26.897Z
started_at: 2026-11-08T09:53:45.590Z
---
A diagnostic ownership-fix smoke compared installed11db with source48be using independent catalog-only seeds and target310, eighteenth among29Open rows. The control had a core at initial classification; the candidate did not, and eight nearby Open rows remained deferred while later catalog cores accumulated. The candidate eventually warmed all314 cores and served the prepared target in77ms. This is not a matched speed comparison or proven regression. Reproduce with alternating trials and record initial prefix replacement, cancellation, provider attempts, lease deadlines and cursor scheduling. Test the hypothesis that a canceled priming cohort retains its attempt lease and deferred members wait behind the All traversal. Fix only if measurements/production-session evidence establish a useful change; preserve source/reader isolation, bounded attempts and fairness for later rows.

## Notes

November 8: focused correction committed as ea1c5ace26195bcf7205275c40f3c516dea9c4ce on codex/v012-navigation-performance-20261108, based on merged main9416. Both same-identity cancellation sites corrected; traversal still restarts/re-primes. Source, reader and epoch replacement/disposal retain exact-owner cancellation; backend/attempt leases unchanged. Production session adds three retained prefix cases and four revoked identity/disposal cases; seven focused Python cases, eight existing golden sections, Biome and both browser type configs pass. Independent strong-tier senior/correctness/performance review now assigned. Full verify, PR/CI, merge and installation remain pending; no timing improvement claimed. QA record and Pulls plan updated; mb-itzy stays paused.

Evidence provenance correction: initial backend diagnostic imported an older editable checkout and is invalid. Its original diagnostic hashes/claims are retained; initial raw JSON was overwritten before preservation and is not reconstructed. Fresh controls pinned to current src assert every imported module path/hash and pass. Direct-path production JS evidence remains valid. See diagnostic.json and diagnostic.wrong-source.invalid.json in b0aq-mechanism-20261108.
