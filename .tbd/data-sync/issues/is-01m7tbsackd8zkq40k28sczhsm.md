---
type: is
id: is-01m7tbsackd8zkq40k28sczhsm
title: Pulls tab says '#N is not listed under Closed' instead of listing it
kind: bug
status: closed
priority: 2
version: 6
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T16:56:07.314Z
updated_at: 2026-11-19T19:07:01.471Z
started_at: 2026-11-19T16:56:37.177Z
closed_at: 2026-11-19T19:07:01.469Z
close_reason: "PR #611 merged"
resolution: null
duplicate_of: null
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


Review B on #611 (2026-11-19, head 721198d7d), answered on the branch after merging origin/main 2af1577eb:
- B-M1 (the owner's path): a list already on All now moves to the pull request's own state's list when All's drawn rows do not reach it (placeSought: target = filter === state || !reach ? state : "all"). Closed, then #2950 (All), then open #1000 now goes to Open and reveals it, where it used to stay on All with "not among the pull requests loaded". A closed #1500 named under All moves to Closed, which notes it too.
- B-L2: a revealPending flag (set by seek, cleared in revealRow(sought)) replaces placing in poll's and loadWindow's reveal checks, so a destination list whose first read fails reveals the row at the next read that brings it, once.
- B-L3: deps.listHasFocus became deps.focusPlace() ("list" | "body" | "elsewhere"). refocus is captured when focus is in the list, and revealRow focuses only when focus is not "elsewhere" when the row arrives.
- B-L4: cancelReads aborts soughtRead (pause, hidden, setShown(false), filter change), and the next poll asks again.
- B-L5: a 4xx lookup that is not pin_changed (after past MAX_PULL_REQUEST_NUMBER) is answered from the newest row: found when it is that number, otherwise absent. It is not re-asked.
- B-L7: the session has steps for a stale lookup after a newer navigation, a lookup let go by the reader's filter choice, a hidden panel, a failed first read after the move, a late refocus (focus elsewhere vs on body), and the refused #9999999999.
- Side effect: revealPending also reveals a pull request opened since the catalog's last read when a later poll of the shown list brings its row, pinned in the crawling story. This covers part of mb-97s2. Its other case is still open: when the PR's own state's list is not the filter shown, the PR stays noted and the list does not move.
- The depth stories moved to their own session part, node tests/dom/nav-reveal-session.js pulls-depth, which the golden runs as its own block ("Beyond the Rows Read"). In one block the transcript failed tryscript with "Regular expression too large".
- Against the previous controller, the new steps differ for B-M1, B-L2, B-L4, B-L5 and the newer-PR reveal. With the focus guard removed, the B-L3 step differs.
- B-L1 (reach bound with interleaved issue numbers) and B-L6 were skipped per the coordinator.
- Head after review B: e85eb3426 (commit on top of the origin/main merge fa1e17c79), pushed. PR #611 title and body updated. Tests: make -o install lint-check passed twice (the second on the final tree); all 100 goldens passed; tests/test_nav_reveal_chrome.py, test_github_pulls_panel_session.py, test_pulls_nav.py, test_github_pulls.py, test_docs_discipline.py, test_github_pulls_stacks_chrome.py and test_github_pulls_row_lines_chrome.py ran 281 passed and 1 failed. The failure was test_github_pulls_stacks_chrome: it timed out waiting for the first .github-pulls-item at load average ~77, on a path with no navigated pull request, and passed on rerun. Full make verify was not run. Not merged.
