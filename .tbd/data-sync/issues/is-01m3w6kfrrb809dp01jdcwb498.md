---
type: is
id: is-01m3w6kfrrb809dp01jdcwb498
title: "After about five full page loads in one tab, the next page waits for a connection: pages in the back/forward cache keep their event stream open"
kind: bug
status: in_progress
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m402f1j3r01mrjj2adyczdpm
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T17:01:14.875Z
updated_at: 2026-10-03T05:05:52.706Z
started_at: 2026-10-01T17:25:22.341Z
---
Found 2026-10-01 while running the new browser step 3.4 of docs/qa-v012-repository-library.md on the stack tip 373b59a9 (a plain trusted folder, `metab <folder> --no-open`), driven in stock Chrome 152.0.7977.83, headless, over the DevTools protocol with `Page.navigate` for each address.

Observed. After about five full page loads in one tab (each a different `/view/<file>` address, loaded as a new document rather than by a click in the tree), the next page's requests wait for a connection before they are sent:

- In a ten-address sequence the sixth page was ready after 4,460 ms where the others took 130 to 370 ms; `/api/file`, `/api/git/repo`, `/api/catalog` and `/api/tree?depth=0` each waited 3.8 to 4.4 s. With Chrome started with `--disable-features=BackForwardCache` the same sequence had no wait (320 to 750 ms per page).
- In the full walk of step 3.4 (Markdown, source anchors, then images) the sixth document's requests waited 50.8 s (`/plugin-static/image/styles.css`, `/plugin-static/image/index.js`, `/api/git/repo`, `/api/catalog`, `/api/tree?depth=0`; Resource Timing `sendStart` about 50,850 ms), and the page logged `metabrowser plugin asset failed to load: /plugin-static/image/styles.css (timed out)` from the 10 s bound in `static/plugin-sdk.js` (`_pluginAssetLoadTimeoutMs`). That error appeared in three of five full walks; twice the image view itself stayed on "Loading preview…" past a 30 s wait.
- The server was idle throughout: no `slow server request` line in its log.

Likely cause (inferred from the code and the bfcache comparison, not proven by a fix). Every page opens `new EventSource("/api/events?scope=root-depth-2")` (`static/app.js`, `inventoryEventSource`). A page that enters the back/forward cache keeps that connection: the `pagehide` handler returns early for a persisted hide and nothing closes the stream. Chrome allows six HTTP/1.1 connections per host, so five cached pages plus the current page's own stream leave none for its other requests until Chrome evicts a cached page. The DevTools log showed one `/api/events` request per loaded document and no close for any of them.

Not a v0.12 regression as far as the code shows: `origin/main` (6c278f3f, v0.11.0) has the same `EventSource` and the same `pagehide` handler. It was not run on 0.11.0. PR #248 chose to keep pin pages eligible for the back/forward cache, which is what makes this reachable on a served mirror too.

Not checked: a headed browser with typed addresses; Safari and Firefox; a served pin.

Fix direction (for whoever takes this; no code was changed): close the event stream on a persisted `pagehide` and reopen it on the matching `pageshow`, as the keyboard infrastructure is rebuilt there, and add a browserless session for it. Acceptance: ten full page loads in one tab with the back/forward cache on, none waiting for a connection.

Until then the runbook's step 3.4 tells the walker to open a new tab if a page stalls.

## Notes

2026-10-01 (coordinator): taken OUT of the v0.12 landing stack; no longer a landing gate. Draft PR #262 (codex/v012-page-connections, a7f7c8bc) fixes the stall, and its independent review found it sound but not safe to land with the stack: P1, Back onto a page with a type filter un-filters the tree (the reconnect snapshot's applyCellPatch, app.js:7174-7298, inserts folder rows and overwrites aggregates regardless of the filter; an old reconnect defect that the fix makes happen on every Back or Forward landing). P2, a landing on a large folder parses a 1.3 MB snapshot and a 292 KB catalog because catalog-feed.js:81 uses a plain fetch that never surfaces a 304 (one long task per landing; base makes no request), and the session's 304 double hides it. P2, five real bugs the tests would not catch (second persisted pagehide clears parked; park leaves the reconnect timer; park keeps the closed stream's reference; a connecting stream is not parked; restore keeps the old error count), caught by three more scenarios. P3: a truncated or deleted live-tail file stays 'Live' after a restore; tasks between pagehide and freeze can open an unparked stream; pendingTallyWatchdog stays dead after a restore; the filter bar is rebuilt on every landing and drops focus; shown() has no per-resume try/catch. Facts established: v0.11.0 has the same stall (sixth page ready after about 57 s); a served mirror or pin opens no event stream and was never affected, so v0.12's View file and pin switches do not reach it; it is reachable only on a plain folder whose addresses are opened as full page loads in one tab. Reason for the decision: the user's requirement that the stack lands without destabilizing regular pages; leaving the fix out keeps regular-page behavior exactly as v0.11.0. To finish after landing: fix the P1 and P2s, prefer skipping the resync when the snapshot's engine version is unchanged, add the three scenarios, then merge on its own. The reviewer's scripts were in the session scratchpad (review-262/).

2026-10-01 (coordinator): raised to P2 and made a landing gate. v0.12 adds full page loads to ordinary use (View file links from a diff, pin switches, Back after a switch), so a stall after about five page loads in one tab is reachable in normal GitHub browsing even if the EventSource code is the same on main. The fix agent must first establish whether 0.11.0 shows it, and prove the cause before fixing.
