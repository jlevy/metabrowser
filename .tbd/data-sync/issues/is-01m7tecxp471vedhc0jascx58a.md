---
type: is
id: is-01m7tecxp471vedhc0jascx58a
title: Pulls list never reveals a pull request newer than the catalog once a poll brings it in
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-11-19T17:41:46.817Z
updated_at: 2026-11-19T19:04:39.297Z
---
From review A on #611 (L7, predates it): a pull request created after the last refresh, named by a navigation, gets 'not in this list'; when a later poll brings its row in, the note goes but the row is not revealed, because only a list's first poll reveals and the chase looks only at older numbers (pulls-panel.js createPullsController).

## Notes

Review C on #611 (2026-11-19): #611 reveals a PR newer than the catalog when the shown list's own poll brings it in (filter = its state). Still open: with the list on the other filter (e.g. Closed, link to a just-opened PR), placeSought rules it absent for good (placing=false ~pulls-panel.js:1825), so the list never moves and the note 'not in this list' stays after the catalog gains it — the owner's original symptom. Fix: treat absent as provisional; re-ask at each poll (two local one-row reads) or when the shown list's generation changes, then place as usual. Also from review C, Low: the note flickers on each reachedEnd page while scrolling (b).
