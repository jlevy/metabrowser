---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Pulls Panel

The Pulls tab lists the repository’s pull requests, newest first, from the cache at
once, and refreshes in the background only while it is shown.
A mirror reads the list ahead of the tab, once and with nothing fetched.
Opening the tab asks for the refresh, which the server holds to one attempt a window,
and a panel with nothing yet waits in the shape of rows, saying why only when the wait
is long. Each filter is its own list, read when it is first chosen and kept.
Reaching the end of what is held reads the next window, and past that the next GitHub
page. A failed refresh leaves the rows and says what to do.
A poll reads the top window with its tag, however many rows are held, so an unchanged
list is a `304`; only an answer from another list file has the whole range held read
again, once, and a window that lands while a poll is out is kept.

The rows walk by key: each press moves two marks, and a key held down reads nothing and
opens nothing until it stops, so a walk of forty rows costs one read.
A key’s open replaces the history entry, and a click’s pushes one.
The newest opening wins and an older read is let go, and Back while a row still waits
for its record keeps that row from opening.
A row following the address is not a selection, and fetches nothing; further windows are
read to reach it only in All, since Open or Closed may not hold it.

This browserless session loads the production `builtin_plugins/github/pulls-panel.js`
and plays the server’s side from `tests/fixtures/github-pulls-panel-responses.json`:
what the in-process application answered of `tests/github_pull_fixture.py`’s stand-in,
with full-size pages.
`tests/test_github_pulls_panel_session.py` replays that story and fails when the
recording drifts.
Timers, the clock, visibility, and paint are injected, and each request
waits for the step to answer it.
Each step prints the requests the panel made, the timer it left, the row marks it made,
what it opened, how many times it painted, and, where the step is about it, what it
would paint. `failures` is what the panel says for each way a refresh can end, and `cap`
at the most rows a list may hold.
`hostile` is a row whose text is markup: it stays a string, and paint writes it as text.
`landing` is what the list’s own address says, and why when there is nothing to select.
`reader` is the page a selection opens, on what a server answers of a record: only a
page a reader chose fetches, a key stopping on a row waits a moment so that tapping past
spends nothing, a key still held keeps the page it opened waiting however long, and past
the bound on jobs it says why and offers **Fetch**. `paint` is the list built in a
stand-in for the DOM: a tree of one level whose rows are its items, a title written as
markup painted as one text node, an append that builds, ages, and keys only the rows it
adds, and ages told again in place as time passes.

```console
$ node tests/dom/github-pulls-panel-session.js
{
  "steps": [
    {
      "step": "the tab is not open: the list is read once, for later",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "painted": 1
    },
    {
      "step": "nothing is cached, and nothing asks to fetch it",
      "requests": [],
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "absent",
        "skeleton": true,
        "listName": "Pull requests of octo/demo"
      }
    },
    {
      "step": "the tab opens: its first read is a 304",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-1\""
      ],
      "painted": 0
    },
    {
      "step": "so the refresh is asked for",
      "requests": [
        "POST /api/plugin/github/pulls-refresh {\"state\":\"all\"}"
      ],
      "timer": "slow",
      "painted": 0,
      "paint": {
        "filter": "all",
        "status": "absent",
        "skeleton": true,
        "listName": "Pull requests of octo/demo"
      }
    },
    {
      "step": "the refresh started; the panel waits in the shape of rows",
      "requests": [],
      "timer": "fast",
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "pending",
        "skeleton": true,
        "listName": "Pull requests of octo/demo",
        "live": "Waiting for the list of pull requests…"
      }
    },
    {
      "step": "a fast poll while it runs",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "timer": "fast",
      "painted": 0
    },
    {
      "step": "a long wait says why it may be waiting",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-2\""
      ],
      "timer": "fast",
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "pending",
        "skeleton": true,
        "listName": "Pull requests of octo/demo",
        "notice": {
          "severity": null,
          "text": "Still waiting for the list… Pull requests being fetched go first.",
          "retry": false
        },
        "live": "Waiting for the list of pull requests…"
      }
    },
    {
      "step": "the list arrives, newest first",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-2\""
      ],
      "timer": "slow",
      "marks": [
        "anchor null -> 106"
      ],
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "current",
        "listName": "Pull requests of octo/demo: 100 pull requests · GitHub has more",
        "count": "100 pull requests · GitHub has more",
        "freshness": "Fetched just now by octo-reader",
        "loadMore": "ready",
        "live": "Pull requests of octo/demo: 100 pull requests · GitHub has more",
        "rowsHeld": 100,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Merged] Say more in the guide | #8 · maintainer · topic ← guide-more | /pull/8",
          "[Open] Count to two in the app | #7 · forker · topic ← forker:count-to-two | /pull/7"
        ]
      }
    },
    {
      "step": "hidden: no timer",
      "requests": [],
      "painted": 0
    },
    {
      "step": "shown again: one read, and a 304 paints nothing",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-3\""
      ],
      "timer": "slow",
      "painted": 0
    },
    {
      "step": "the page is hidden: no timer",
      "requests": [],
      "painted": 0
    },
    {
      "step": "the page is shown again: it polls at once",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-3\""
      ],
      "timer": "slow",
      "painted": 0
    },
    {
      "step": "the end of the list asks for the next page",
      "requests": [
        "POST /api/plugin/github/pulls-refresh {\"state\":\"all\",\"more\":true}"
      ],
      "timer": "slow",
      "painted": 1
    },
    {
      "step": "Load more says it is loading",
      "requests": [],
      "timer": "fast",
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "current",
        "listName": "Pull requests of octo/demo: 100 pull requests · GitHub has more",
        "count": "100 pull requests · GitHub has more",
        "freshness": "Refreshing… · fetched just now by octo-reader",
        "loadMore": "loading",
        "live": "Pull requests of octo/demo: 100 pull requests · GitHub has more",
        "rowsHeld": 100,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Merged] Say more in the guide | #8 · maintainer · topic ← guide-more | /pull/8",
          "[Open] Count to two in the app | #7 · forker · topic ← forker:count-to-two | /pull/7"
        ]
      }
    },
    {
      "step": "still reading it",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "timer": "fast",
      "painted": 0
    },
    {
      "step": "it is in, and the next window of rows is asked for",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-4\"",
        "GET /api/plugin/github/pulls?state=all&limit=100&after=7"
      ],
      "painted": 1
    },
    {
      "step": "the rows after the first window are appended",
      "requests": [],
      "timer": "slow",
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "current",
        "listName": "Pull requests of octo/demo: 102 pull requests",
        "count": "102 pull requests",
        "freshness": "Fetched just now by octo-reader",
        "live": "Pull requests of octo/demo: 102 pull requests",
        "rowsHeld": 102,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Open] Work item 6 | #6 · contributor · topic ← work-6 | /pull/6",
          "[Open] Work item 5 | #5 · contributor · topic ← work-5 | /pull/5"
        ]
      }
    },
    {
      "step": "a complete list asks for nothing more",
      "requests": [],
      "timer": "slow",
      "painted": 0
    },
    {
      "step": "the next poll reads the top window, and it is unchanged",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-5\""
      ],
      "timer": "slow",
      "painted": 0
    },
    {
      "step": "Open is chosen",
      "requests": [
        "GET /api/plugin/github/pulls?state=open&limit=100"
      ],
      "timer": "fast",
      "marks": [
        "anchor 106 -> null"
      ],
      "filterChanged": [
        "open"
      ],
      "painted": 1
    },
    {
      "step": "its own rows: a draft and an open one",
      "requests": [],
      "timer": "slow",
      "marks": [
        "anchor null -> 10"
      ],
      "painted": 1,
      "paint": {
        "filter": "open",
        "status": "current",
        "listName": "Pull requests of octo/demo: 2 pull requests",
        "count": "2 pull requests",
        "freshness": "Fetched just now by octo-reader",
        "live": "Pull requests of octo/demo: 2 pull requests",
        "rowsHeld": 2,
        "rows": [
          "[Draft] WIP: draft the next page | #10 · maintainer · topic ← wip | /pull/10",
          "[Open] Count to two in the app | #7 · forker · topic ← forker:count-to-two | /pull/7"
        ]
      }
    },
    {
      "step": "All again paints what it held at once",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-5\""
      ],
      "timer": "slow",
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "current",
        "listName": "Pull requests of octo/demo: 102 pull requests",
        "count": "102 pull requests",
        "freshness": "Fetched just now by octo-reader",
        "live": "Pull requests of octo/demo: 102 pull requests",
        "rowsHeld": 102,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Open] Work item 6 | #6 · contributor · topic ← work-6 | /pull/6",
          "[Open] Work item 5 | #5 · contributor · topic ← work-5 | /pull/5"
        ]
      }
    },
    {
      "step": "and its read is a 304",
      "requests": [],
      "timer": "slow",
      "painted": 0
    },
    {
      "step": "a filter left before it answered is let go",
      "requests": [
        "GET /api/plugin/github/pulls?state=closed&limit=100",
        "aborted GET /api/plugin/github/pulls?state=closed&limit=100",
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-5\""
      ],
      "timer": "slow",
      "marks": [
        "anchor 10 -> null",
        "anchor null -> 106"
      ],
      "filterChanged": [
        "closed"
      ],
      "painted": 2
    },
    {
      "step": "All's read is a 304",
      "requests": [],
      "timer": "slow",
      "painted": 0
    },
    {
      "step": "a minute on, the list is stale, and asks",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-5\"",
        "POST /api/plugin/github/pulls-refresh {\"state\":\"all\"}"
      ],
      "timer": "slow",
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "stale",
        "listName": "Pull requests of octo/demo: 102 pull requests",
        "count": "102 pull requests",
        "freshness": "Fetched 1 min ago by octo-reader · may be out of date",
        "live": "Pull requests of octo/demo: 102 pull requests",
        "rowsHeld": 102,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Open] Work item 6 | #6 · contributor · topic ← work-6 | /pull/6",
          "[Open] Work item 5 | #5 · contributor · topic ← work-5 | /pull/5"
        ]
      }
    },
    {
      "step": "it refreshes with its rows in place",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "timer": "fast",
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "stale",
        "listName": "Pull requests of octo/demo: 102 pull requests",
        "count": "102 pull requests",
        "freshness": "Refreshing… · fetched 1 min ago by octo-reader",
        "live": "Pull requests of octo/demo: 102 pull requests",
        "rowsHeld": 102,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Open] Work item 6 | #6 · contributor · topic ← work-6 | /pull/6",
          "[Open] Work item 5 | #5 · contributor · topic ← work-5 | /pull/5"
        ]
      }
    },
    {
      "step": "refreshed: the whole range is read once, and no row repainted",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-12\"",
        "GET /api/plugin/github/pulls?state=all&limit=102"
      ],
      "timer": "slow",
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "current",
        "listName": "Pull requests of octo/demo: 102 pull requests",
        "count": "102 pull requests",
        "freshness": "Fetched just now by octo-reader",
        "live": "Pull requests of octo/demo: 102 pull requests",
        "rowsHeld": 102,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Open] Work item 6 | #6 · contributor · topic ← work-6 | /pull/6",
          "[Open] Work item 5 | #5 · contributor · topic ← work-5 | /pull/5"
        ]
      }
    },
    {
      "step": "offline: the rows show, with what to do",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "timer": "slow",
      "marks": [
        "anchor null -> 106"
      ],
      "painted": 2,
      "paint": {
        "filter": "all",
        "status": "current",
        "listName": "Pull requests of octo/demo: 102 pull requests",
        "count": "102 pull requests",
        "freshness": "Fetched just now by octo-reader",
        "notice": {
          "severity": "warning",
          "text": "Offline, or GitHub could not be reached. The list is as it was last fetched.",
          "retry": true
        },
        "loadMore": "ready",
        "live": "Offline, or GitHub could not be reached. The list is as it was last fetched.",
        "rowsHeld": 100,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Merged] Say more in the guide | #8 · maintainer · topic ← guide-more | /pull/8",
          "[Open] Count to two in the app | #7 · forker · topic ← forker:count-to-two | /pull/7"
        ]
      }
    },
    {
      "step": "Retry asks as a reader",
      "requests": [
        "POST /api/plugin/github/pulls-refresh {\"state\":\"all\",\"retry\":true}"
      ],
      "timer": "slow",
      "painted": 0
    },
    {
      "step": "the retry is under way",
      "requests": [],
      "timer": "fast",
      "painted": 1
    },
    {
      "step": "rate limited: no Retry, and when it lifts",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "timer": "slow",
      "marks": [
        "anchor null -> 106"
      ],
      "painted": 2,
      "paint": {
        "filter": "all",
        "status": "current",
        "listName": "Pull requests of octo/demo: 102 pull requests",
        "count": "102 pull requests",
        "freshness": "Fetched just now by octo-reader",
        "notice": {
          "severity": "warning",
          "text": "GitHub's rate limit lifts at 2026-09-23T16:46:00.000Z. No automatic attempt runs before then.",
          "retry": false
        },
        "loadMore": "ready",
        "live": "GitHub's rate limit lifts at 2026-09-23T16:46:00.000Z. No automatic attempt runs before then.",
        "rowsHeld": 100,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Merged] Say more in the guide | #8 · maintainer · topic ← guide-more | /pull/8",
          "[Open] Count to two in the app | #7 · forker · topic ← forker:count-to-two | /pull/7"
        ]
      }
    },
    {
      "step": "a server with no GitHub repository",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "timer": "slow",
      "painted": 2,
      "paint": {
        "filter": "all",
        "status": "absent",
        "listName": "Pull requests",
        "empty": "This server serves no GitHub repository.",
        "live": "This server serves no GitHub repository."
      }
    },
    {
      "step": "a mirror's read ahead: a stale list asks",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100",
        "POST /api/plugin/github/pulls-refresh {\"state\":\"all\"}"
      ],
      "marks": [
        "anchor null -> 106"
      ],
      "painted": 2
    },
    {
      "step": "and nothing polls a list that is not shown",
      "requests": [],
      "painted": 1
    },
    {
      "step": "the first row takes Tab when none is current",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "timer": "slow",
      "marks": [
        "anchor null -> 106"
      ],
      "painted": 2
    },
    {
      "step": "Up at the first row is clamped: no row opens",
      "requests": [],
      "timer": "slow",
      "painted": 0,
      "handled": true
    },
    {
      "step": "one press reads the row's record at once",
      "requests": [
        "GET /api/plugin/github/pull?number=105"
      ],
      "timer": "slow",
      "marks": [
        "anchor 106 -> 105 focus",
        "current null -> 105"
      ],
      "painted": 0
    },
    {
      "step": "and opens it, with what it read",
      "requests": [],
      "timer": "slow",
      "opened": [
        {
          "number": 105,
          "tab": "",
          "history": "replace",
          "fetchAfterMs": 500,
          "initial": "the record read for it"
        }
      ],
      "painted": 0
    },
    {
      "step": "a key held for 40 rows",
      "requests": [],
      "timer": "slow",
      "marks": 80,
      "painted": 0
    },
    {
      "step": "the key is let go",
      "requests": [
        "GET /api/plugin/github/pull?number=65"
      ],
      "timer": "slow",
      "painted": 0
    },
    {
      "step": "the row it stopped on opens",
      "requests": [],
      "timer": "slow",
      "opened": [
        {
          "number": 65,
          "tab": "",
          "history": "replace",
          "fetchAfterMs": 500,
          "initial": "the record read for it"
        }
      ],
      "painted": 0
    },
    {
      "step": "a key's release that was not seen: the wait opens it",
      "requests": [
        "GET /api/plugin/github/pull?number=63"
      ],
      "timer": "slow",
      "marks": [
        "anchor 65 -> 64 focus",
        "current 65 -> 64",
        "anchor 64 -> 63 focus",
        "current 64 -> 63"
      ],
      "painted": 0
    },
    {
      "step": "two presses: the older read is let go",
      "requests": [
        "aborted GET /api/plugin/github/pull?number=63",
        "GET /api/plugin/github/pull?number=62",
        "aborted GET /api/plugin/github/pull?number=62",
        "GET /api/plugin/github/pull?number=61"
      ],
      "timer": "slow",
      "marks": [
        "anchor 63 -> 62 focus",
        "current 63 -> 62",
        "anchor 62 -> 61 focus",
        "current 62 -> 61"
      ],
      "painted": 0
    },
    {
      "step": "and only the newest opens",
      "requests": [],
      "timer": "slow",
      "opened": [
        {
          "number": 61,
          "tab": "",
          "history": "replace",
          "fetchAfterMs": 500,
          "initial": "the record read for it"
        }
      ],
      "painted": 0
    },
    {
      "step": "Back while a row waits for its record: that row does not open",
      "requests": [
        "GET /api/plugin/github/pull?number=60"
      ],
      "timer": "slow",
      "marks": [
        "anchor 61 -> 60 focus",
        "current 61 -> 60",
        "current 60 -> 70",
        "anchor 60 -> 70"
      ],
      "reveals": [
        70
      ],
      "painted": 0
    },
    {
      "step": "the address names another row",
      "requests": [],
      "timer": "slow",
      "marks": [
        "current 70 -> 90",
        "anchor 70 -> 90"
      ],
      "reveals": [
        90
      ],
      "painted": 0
    },
    {
      "step": "the address names no row",
      "requests": [],
      "timer": "slow",
      "marks": [
        "current 90 -> null"
      ],
      "painted": 0
    },
    {
      "step": "a pointer rests on a row: one read",
      "requests": [
        "GET /api/plugin/github/pull?number=80"
      ],
      "timer": "slow",
      "marks": [
        "current null -> 90"
      ],
      "reveals": [
        90
      ],
      "painted": 0
    },
    {
      "step": "the click opens at once, with no second read",
      "requests": [],
      "timer": "slow",
      "marks": [
        "current 90 -> 80",
        "anchor 90 -> 80"
      ],
      "opened": [
        {
          "number": 80,
          "tab": "",
          "history": "push",
          "fetchAfterMs": 0,
          "initial": "the record read for it"
        }
      ],
      "painted": 0
    },
    {
      "step": "the current row is not in the first window",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100",
        "GET /api/plugin/github/pulls?state=all&limit=100&after=7"
      ],
      "timer": "slow",
      "marks": [
        "anchor null -> 106"
      ],
      "painted": 2
    },
    {
      "step": "the next window holds it, and it is brought into view",
      "requests": [],
      "timer": "slow",
      "marks": [
        "anchor 106 -> 5"
      ],
      "reveals": [
        5
      ],
      "painted": 1
    },
    {
      "step": "in Closed, a row past the first window is not chased",
      "requests": [
        "GET /api/plugin/github/pulls?state=closed&limit=100"
      ],
      "timer": "slow",
      "marks": [
        "anchor null -> 1000"
      ],
      "painted": 2
    },
    {
      "step": "a window and a poll are both asked for",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100&after=7",
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-5\""
      ],
      "painted": 0
    },
    {
      "step": "the window lands first, and the poll reads the whole range",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=102"
      ],
      "painted": 1
    },
    {
      "step": "so no row the window added is dropped",
      "requests": [],
      "timer": "slow",
      "painted": 0,
      "rowsHeld": 102
    },
    {
      "step": "dispose lets the read go",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100",
        "aborted GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "painted": 1,
      "timers": []
    }
  ],
  "failures": {
    "not_logged_in": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "Run gh auth login to read this repository's pull requests.",
        "retry": true
      }
    },
    "gh_too_old": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "This gh is too old to report its account; install gh 2.81.0 or newer.",
        "retry": true
      }
    },
    "not_found_or_private": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "The repository was not found, or the signed-in account cannot read its pull requests.",
        "retry": true
      }
    },
    "network_error": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "Offline, or GitHub could not be reached. The list is as it was last fetched.",
        "retry": true
      }
    },
    "gh_failed": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "GitHub answered with something other than JSON.",
        "retry": true
      }
    },
    "account_changed": {
      "status": "stale",
      "freshness": "Fetched just now by octo-reader · may be out of date",
      "notice": {
        "severity": "warning",
        "text": "The active gh account changed during the read, so what was read is discarded; open the list again.",
        "retry": true
      }
    },
    "gh_missing": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "Install GitHub CLI and sign in to read this repository's pull requests.",
        "retry": true
      }
    },
    "rate_limited": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "GitHub's rate limit lifts at 2026-09-23T16:46:00.000Z. No automatic attempt runs before then.",
        "retry": false
      }
    },
    "cache_unwritable": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "The list of pull requests could not be written to the cache.",
        "retry": true
      }
    }
  },
  "cap": {
    "count": "1,000 pull requests · GitHub has more",
    "listName": "Pull requests of octo/demo: 1,000 pull requests · GitHub has more",
    "loadMore": null,
    "github": "https://github.com/octo/demo/pulls",
    "notice": {
      "severity": "warning",
      "text": "Some rows were cut to fit, or could not be read.",
      "retry": false
    }
  },
  "hostile": {
    "number": 7,
    "href": "/pull/7",
    "state": "merged",
    "stateLabel": "Merged",
    "title": "<img src=x onerror=\"alert(1)\"> & \"quotes\"",
    "author": "ghost",
    "updatedAt": "2026-09-17T12:00:00Z",
    "refs": "main ← <b>topic</b> (deleted fork)",
    "meta": "#7 · ghost · main ← <b>topic</b> (deleted fork)"
  },
  "spelled": "main ← topic",
  "landing": {
    "a server with no repository": "This server serves no GitHub repository.",
    "a mirror": "Select a pull request.",
    "a list with no rows, and no gh": "Install GitHub CLI and sign in to read this repository's pull requests."
  },
  "reader": [
    {
      "name": "an address alone fetches nothing",
      "asked": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "waits": [
        30000
      ],
      "before": {
        "message": "This pull request has not been fetched yet.",
        "canRefresh": true
      },
      "after": {
        "message": "This pull request has not been fetched yet.",
        "canRefresh": true
      }
    },
    {
      "name": "a click on a row with no record fetches it at once",
      "asked": [
        "GET /api/plugin/github/pull?number=7",
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true}"
      ],
      "waits": [
        30000,
        0
      ],
      "before": {
        "message": "Fetching the pull request…",
        "canRefresh": false
      },
      "after": {
        "message": "Fetching the pull request…",
        "canRefresh": false
      }
    },
    {
      "name": "a key stopping on one waits, so tapping past it spends nothing",
      "asked": [
        "GET /api/plugin/github/pull?number=7",
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true}"
      ],
      "waits": [
        30000,
        500
      ],
      "before": {
        "message": "Fetching the pull request…",
        "canRefresh": false
      },
      "after": {
        "message": "Fetching the pull request…",
        "canRefresh": false
      }
    },
    {
      "name": "a key still held waits out the page it opened, however long: it fetches nothing",
      "asked": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "waits": [
        30000,
        500
      ],
      "before": {
        "message": "Fetching the pull request…",
        "canRefresh": false
      },
      "after": {
        "message": "Fetching the pull request…",
        "canRefresh": false
      },
      "once let go": {
        "asked": [
          "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true}"
        ],
        "message": "Fetching the pull request…"
      }
    },
    {
      "name": "past the bound on jobs it says why, and offers Fetch",
      "asked": [
        "GET /api/plugin/github/pull?number=7",
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true}"
      ],
      "waits": [
        30000,
        0
      ],
      "before": {
        "message": "Fetching the pull request…",
        "canRefresh": false
      },
      "after": {
        "message": "The refresh was refused (too many pull requests are being fetched; try again when one has finished).",
        "canRefresh": true
      }
    },
    {
      "name": "a row with a record fetches nothing",
      "asked": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "waits": [
        30000
      ],
      "before": {
        "message": null,
        "canRefresh": false
      },
      "after": {
        "message": null,
        "canRefresh": false
      }
    }
  ],
  "paint": {
    "the list": "ul .github-pulls-list role=\"tree\" aria-label=\"Pull requests of octo/demo: 102 pull requests\"",
    "a row": [
      "li .github-pulls-item role=\"none\"",
      "a .github-pulls-row href=\"/pull/106\" role=\"treeitem\" aria-level=\"1\" tabindex=\"-1\""
    ],
    "the row whose page is shown": "a .github-pulls-row.selected href=\"/pull/105\" role=\"treeitem\" aria-level=\"1\" tabindex=\"0\" aria-current=\"page\" aria-selected=\"true\"",
    "its parts": [
      "span .github-pull-state-icon role=\"img\" aria-label=\"Open\"",
      "span .github-pulls-title",
      "span .github-pulls-age.age-hour",
      "span .github-pulls-meta"
    ],
    "a title written as markup is one text node": [
      {
        "node": "#text",
        "data": "<img src=x onerror=\"alert(1)\"> & <b>bold</b>"
      }
    ],
    "rows built for the first window": 100,
    "a window of 2 appended to 100: rows built, aged, keyed": [
      2,
      2,
      2
    ],
    "rows held": 102,
    "an age, before": "2h",
    "an age, two hours on": "4h",
    "rows built to tell it": 0,
    "disposed: what is left in the tab": 0
  }
}
? 0
```
