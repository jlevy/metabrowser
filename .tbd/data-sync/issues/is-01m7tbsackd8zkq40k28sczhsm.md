---
type: is
id: is-01m7tbsackd8zkq40k28sczhsm
title: Pulls tab says '#N is not listed under Closed' instead of listing it
kind: bug
status: in_progress
priority: 2
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T16:56:07.314Z
updated_at: 2026-11-19T18:00:25.063Z
started_at: 2026-11-19T16:56:37.177Z
---
Owner, 2026-11-19, verbatim: "also I see this on the PR tab for trading repo / 1,118 PRs on finterm-ai/trading / Updated just now / #1175 is not listed under Closed. / what is it putting an extra message about #1175 for? Why is it not listed? Having random messages to explain bugs makes no sense. If this is a bug, we should fix it. If it is not a bug, we should understand why it would not be listed." Find why the shown pull request is missing from the Closed list; fix the cause rather than explaining it with a notice.

## Notes

Root cause (2026-11-19): not a data bug. #1175 is OPEN (draft): gh pr view 1175 --repo finterm-ai/trading gives state OPEN, closedAt/mergedAt null. The running server (127.0.0.1:8411) holds it in GET /api/plugin/github/pulls?state=open (state open, draft true) and not in ?state=closed (total 1021, complete true). The reader had the Closed filter while #1175 was shown, so Closed correctly left it out. The note came from pulls-panel.js outsideText, the mb-6y0g rule "A reveal never changes the filter ... a pull request the list does not hold is named under its band". It stated neither the reason nor a remedy, so it read as a bug excuse.

Change (PR https://github.com/jlevy/metabrowser/pull/611, branch claude/pulls-unlisted-1175, unmerged; owner to decide the design): a navigation (link, Quick Search, Back, stack key, address) to a pull request that Open or Closed leaves out switches the list to All and reveals it there (widenForSought). The list decides once it has read past the number or the other state's list holds it. A filter the reader picks is respected silently. Open and Closed now reveal a navigated PR found while filling past the first window. Notes remain only for a navigated PR the list still cannot show: older than DISPLAY_ROWS (500) rows, "not among the pull requests loaded", or read past under All, "not in this list".

Not done: chasing past DISPLAY_ROWS (would need a measurement). Full make verify not run locally (machine loaded); lint-check, all 100 goldens, nav-reveal Chrome, and the pulls panel and Chrome tests passed.

Review A on #611 (2026-11-19; owner approved landing after review), answered at 721198d7d on head fae88eba1:
- M1: placement now comes from the catalog, not windows read. readSought makes two one-row indexed reads, ?state=all&limit=1&after=N+1 and ?state=all&limit=1 (the newest). The list moves to All when newest-N < All's display limit, otherwise to the PR's own state's list. Open #1000 under Closed now goes to Open and is revealed. Nothing is cleared for good at the display limit.
- M2: while the catalog is incomplete, an uncached number is undecided: the list stays, says nothing, and re-asks each poll. "not in this list" requires complete:true.
- L1: a list error no longer ends placing; only not_github does. A failed lookup is re-asked at the next poll.
- L2: if focus was in the list when it moved, the revealed row takes focus (listHasFocus, revealRow). A Chrome step walks from #7's focused row. With refocus disabled, that step fails.
- L3/L4: the pulls-nav.js filterChanged doc, the session header and docs/reviewing-pull-requests.md are updated.
- L6: the Chrome walk is pinned to #8. The session gains crawling and failing stories.
- L5 and L7 were skipped per the coordinator, who will bead them.
Tests: make -o install lint-check passed; all 100 goldens passed; nav-reveal Chrome passed. The pulls panel, pulls-nav, key-reveal, files-tree and pulls Chrome tests passed, as did docs-discipline and user-guide-values (69 passed). Full make verify was not run (machine loaded). Not merged.
