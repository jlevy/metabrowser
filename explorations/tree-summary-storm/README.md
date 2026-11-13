# Root-Summary Request Storm

This fixture measures how often a page asks the server for the root’s tallies,
`GET /api/tree?depth=0`, what each answer costs, and what that does to the Commits tab
in the app’s WKWebView and in Chrome.

## What Happened

A window of the macOS app serving a large repository stopped loading its Commits tab.
The repository had about 12,800 tracked files, 248,000 gitignored files (10 GB), 10,044
commits, and a 261 KB refs list, and was being written to while it was open.
Its server log showed root-summary requests slower than 2 s starting once the first walk
had finished and still arriving fifteen minutes later, at 2 to 8 s each, usually four
arriving within 10 ms of each other.
After the walk a lone root summary answered in milliseconds, and in a Chrome tab Commits
loaded.

## The Cause

Four things compound.

- **Every write asks every page.** Once the walk has finished, each write the watcher
  reports moves the root’s aggregate, and the event stream upserts the root.
  Each root upsert called `scheduleRootSummaryRefresh` in `static/app.js`. During the
  walk the root has no totals yet, so no upsert reaches it, and the storm starts only
  when the walk ends.

- **The page did not wait for its own requests.** The refresh was debounced by 500 ms,
  and it cleared its timer when the timer fired, before the request settled.
  So a page sent another request every half second while the tree kept changing, however
  many were still in flight.

- **Each request was a full pass, after the one before it.** On a settled index whose
  revision is moving, every root summary recomputes the tallies, so that an answer
  always counts the write that asked for it.
  A pass over 300,000 entries took 1.7 s, four fifths of it classifying every file
  twice, by name and by extension.
  Requests queued for one pass at a time, so each waited for the pass in progress and
  then ran its own.

- **WebKit sends identical requests in parallel.** WebKit opens six HTTP/1.1 connections
  to a host, shared by every web view in the app, and each page’s event stream holds
  one. It sent a page’s pile of root summaries on every other free connection, so the
  Commits tab’s `/api/git/*` requests waited behind multi-second summaries.
  Chrome holds identical GETs behind its HTTP cache lock and sends them one at a time,
  which left its other connections free; Commits loaded there.

## The Fix

- `createRootSummaryRefresh` in `static/navigation.js` keeps one root-summary request in
  flight per page. An ask while one is in flight or waiting marks the summary stale, and
  one request after it answers them all.
  The next request waits at least 2 s, or twice what the last one took, after the last
  one settled; a failure doubles that, up to 30 s, and asks again.
  A hidden page, or a Files panel behind another tab, asks nothing until it is shown.
  `tests/dom/root-summary-refresh-session.js` runs the shell’s own code for this.

- The provider classifies each distinct extension once per pass rather than every file
  twice (`FileTypeRegistry.classifies_by_name`), and readers that arrive during a pass
  share the one after it (`_read_navigation_sync`), whose image is newer than each of
  their arrivals, so every answer still counts every write made before it was asked.

- The Commits panel retries a repository check that got no answer, at a doubling
  interval up to 30 s, instead of leaving the page without a Commits tab, and only an
  answer that the root is no longer a repository removes the tab.

## Running It

Build a corpus of about 303,000 entries (3,201 tracked files, 300,000 ignored ones,
10,001 commits, and 2,000 refs).
It takes about a minute and about 100 MB:

```shell
explorations/tree-summary-storm/make-corpus.sh /tmp/storm-corpus
```

Build the WebKit driver, then run a trial in each engine.
Each trial starts its own server on the port given, so the first walk is running when
the page loads, appends to two logs in the corpus every 250 ms, and opens the Commits
tab 35 s after navigation, after the walk:

```shell
(cd apps/macos && swift build --product WebKitDriver)
CORPUS=/tmp/storm-corpus LIVE_WRITES=0.25 \
  explorations/tree-summary-storm/run.sh webkit 8931 webkit-live 35000
CORPUS=/tmp/storm-corpus LIVE_WRITES=0.25 \
  explorations/tree-summary-storm/run.sh chrome 8932 chrome-live 35000
# Four pages on one server, as four tabs of a window:
CORPUS=/tmp/storm-corpus LIVE_WRITES=0.25 FRAMES=3 \
  explorations/tree-summary-storm/run.sh webkit 8931 webkit-four 35000
```

`run.sh` serves the corpus with `METABROWSER_REQUEST_LOG=verbose`, loads `probe.js` at
document start through the driver’s `measure` mode or through `chrome.mjs`, and prints
`summarize.mjs`: how many root summaries the page sent and the most it had in flight,
how many reached the server and the most it answered at once, their server times, and
when each Commits request was sent and answered.
`profile_pass.py` times one tally pass over a synthetic index, and `--profile` shows
where it goes.

## Recorded Result

Measured on 2026-11-13 on macOS 26.5.2, in WKWebView (WebKit 21624.2.5.11.8, a debug
`WebKitDriver`) and headless Chrome 152.0.7977.83. Before is commit `f6902b8a`; after is
the fix. Each row is one run, not a back-to-back pair, on a machine with a load average
near 13 from unrelated work, so no time here is a clean one; the differences are ten
times or more.

### After the Walk, with Writes Every 250 ms

The Commits tab opened 35 s after navigation, about 20 s after the walk finished.
Root summaries are counted over the whole run.

| Run | Pages | Summaries sent by the page | Most in flight | Most at the server at once | Server time, median | Commits time to load |
| --- | --- | --- | --- | --- | --- | --- |
| Before, WebKit | 1 | 53 | 10 | 5 | 3,225 ms | 7,566 ms |
| Before, WebKit | 4 | 250 reached the server in 7 min | — | 2 | 3,297 ms | never: no Commits request reached the server in 7 min |
| Before, Chrome | 1 | 36 (14 reached the server) | 23 | 1 | 1,559 ms | 722 ms |
| After, WebKit | 1 | 10 | 1 | 1 | 385 ms | 414 ms |
| After, WebKit | 1 | 10 | 1 | 1 | 392 ms | 428 ms |
| After, WebKit | 4 | 10 (39 from all four reached the server) | 1 | 2 | 406 ms | 464 ms |
| After, Chrome | 1 | 8 | 1 | 1 | 398 ms | 468 ms |

Before, in WebKit with one page, each Commits request waited 1.5 to 3.9 s for a
connection while the server answered it in 0.1 to 0.7 s, and the tab showed its loading
skeleton for 7.5 s. The frames of the four-page runs are not instrumented, so the page
columns count the top page only.

### During the Walk

The same writes, with the Commits tab opened 6 s after navigation, while the walk ran.

| Run | Summaries sent | Commits time to load |
| --- | --- | --- |
| Before, WebKit | 1 | 361 ms |
| Before, Chrome | 1 | 358 ms |
| After, WebKit | 1 | 463 ms |
| After, Chrome | 1 | 357 ms |

### One Tally Pass

`profile_pass.py 300000`, three passes each, the same machine and load:

| Build | One pass over 300,000 entries |
| --- | --- |
| Before | 1,694 to 1,739 ms |
| After | 373 to 374 ms |

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
