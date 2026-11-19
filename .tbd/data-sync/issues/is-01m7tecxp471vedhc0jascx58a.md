---
type: is
id: is-01m7tecxp471vedhc0jascx58a
title: Pulls list never reveals a pull request newer than the catalog once a poll brings it in
kind: bug
status: in_progress
priority: 3
version: 4
delegate: claude-code@macbookpro
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T17:41:46.817Z
updated_at: 2026-11-19T19:26:05.161Z
started_at: 2026-11-19T19:07:25.518Z
---
From review A on #611 (L7, predates it): a pull request created after the last refresh, named by a navigation, gets 'not in this list'; when a later poll brings its row in, the note goes but the row is not revealed, because only a list's first poll reveals and the chase looks only at older numbers (pulls-panel.js createPullsController).

## Notes

Review C on #611 (2026-11-19): #611 reveals a PR newer than the catalog when the shown list's own poll brings it in (filter = its state). Still open: with the list on the other filter (e.g. Closed, link to a just-opened PR), placeSought rules it absent for good (placing=false ~pulls-panel.js:1825), so the list never moves and the note 'not in this list' stays after the catalog gains it — the owner's original symptom. Fix: treat absent as provisional; re-ask at each poll (two local one-row reads) or when the shown list's generation changes, then place as usual. Also from review C, Low: the note flickers on each reachedEnd page while scrolling (b).


Fix (2026-11-19, branch claude/pulls-newer-than-catalog from origin/main 0d949cdfa):
- Medium: "absent" is provisional. placeSought keeps placing for {state:"absent", mark}, and noteOutside shows "not in this list" while it is absent. After a poll, it re-asks (readSought) when catalogMark(shown list's envelope) differs from the mark of the lookup that ruled it absent. catalogMark = epoch (from generation) + catalog_fetched (cached["all"]). Within an epoch that only grows: pull_catalog.py deletes rows only on reset. Once found, it is placed as usual (moves to All or its own state's list and reveals).
  - Not the shown list's generation: pull_catalog.py bumps generations only for "all" and the row's state, so Closed's generation does not change when an open PR arrives.
  - Not every poll: an unchanged catalog is not re-asked, which keeps review B's L5 guarantee for #9999999999.
- Low (b): noteOutside keeps "not among the pull requests loaded" while rows < displayLimit once it has been said (outside === outsideText(current, true)), so a reachedEnd page no longer flickers it; it goes when the row arrives (revealed then).
- Session steps (pulls-depth): under Closed, open #2995 opened since the catalog's last read is noted; an unchanged catalog is not re-asked; after the catalog reads it, Closed's poll re-asks, moves to All and reveals it. #1500 noted under Closed: one reachedEnd page keeps the note; nine more keep it until the page that brings #1500 reveals it. Against main's controller these steps flicker (8 times) and never move for #2995.
- PR https://github.com/jlevy/metabrowser/pull/615, head a84094672 (from origin/main 0d949cdfa), not merged. Tests: make -o install lint-check passed. Goldens: 99 of 100 passed; cli-skill-recipes failed on Before-hook timeouts (30 s) under load and passed alone (17 passed). The nav-reveal/pulls/docs pytest set including Chrome: 283 passed. Full make verify was not run (machine loaded).
