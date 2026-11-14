---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Background Freshness in the Browser

The visible Pulls panel asks the server to prefetch, behind the reader, what they are
likely to open next: after each scan of the repository’s list finishes, once a scan, and
when the reader lands on a row.
It names the anchored row’s neighbours and the top five rows, leaving out the open row,
whose record is its page’s own refresh, and the changed files of the open row and its
neighbours. A scan still running asks nothing of its own; a list whose refresh failed, a
hidden panel, and an offline page ask nothing at all.
While the lane the panel started is reading a row’s record, that row’s title breathes,
as a core batch’s rows do, and only while the panel is live and online.
The panel sends one prefetch request at a time: landings made while one is on its way
wait as one pending ask, sent when it answers, from the row landed on last.

The pull-request page says when the repository’s list last checked a record apart from
when the record was read.
When that check is a window old, the page asks for the list’s next scan before it reads,
once a window, and a 304 carries the next check in its header.
While that scan runs the header says so, and the page polls fast until it ends, so a
change the scan publishes is refreshed within a fast poll.
A record the list never vouched for is refreshed once a window instead.
When the head moved, the page says so over the diff it keeps.

This browserless session loads both production controllers and answers every request at
once; the clock, visibility, the network, and timers are injected.

```console
$ node tests/dom/github-pulls-prefetch-behavior.js
{
  "afterScan": {
    "records": [
      119,
      117,
      120,
      116
    ],
    "files": [
      118,
      119,
      117
    ],
    "changed": true
  },
  "sameScanAsksOnce": true,
  "nextScanAsksAgain": true,
  "afterLanding": {
    "records": [
      111,
      109,
      120,
      119,
      118,
      117,
      116
    ],
    "files": [
      110,
      111,
      109
    ],
    "changed": false
  },
  "breathingWhileRead": [
    111
  ],
  "breathingOffline": [],
  "breathingAfter": [],
  "walkAsksInFlight": 1,
  "walkFiles": [
    [
      115,
      116,
      114
    ],
    [
      113,
      114,
      112
    ]
  ],
  "quiet": {
    "refreshing": 1,
    "failed": 0,
    "hidden": 0,
    "offline": 0
  },
  "firstRead": [
    "GET /api/plugin/github/pull?number=7"
  ],
  "checked": "Checked just now · fetched 3 h ago via GitHub CLI",
  "lapsedRead": [
    "POST /api/plugin/github/pulls-refresh",
    "GET /api/plugin/github/pull?number=7"
  ],
  "checkedAfter304": "Checked just now · fetched 3 h ago via GitHub CLI",
  "withinWindow": [
    "GET /api/plugin/github/pull?number=7"
  ],
  "scanningRead": [
    "POST /api/plugin/github/pulls-refresh",
    "GET /api/plugin/github/pull?number=7"
  ],
  "scanningNextPolls": [
    1000
  ],
  "scanPublishedChange": [
    "GET /api/plugin/github/pull?number=7",
    "POST /api/plugin/github/pull-refresh"
  ],
  "afterScanPolls": [
    30000
  ],
  "pendingChecks": [
    "GET /api/plugin/github/pull?number=7",
    "POST /api/plugin/github/pull-refresh"
  ],
  "pendingFreshness": "Fetched 3 h ago via GitHub CLI",
  "headMoved": "New commits were pushed; updating.",
  "headMovedOffline": "New commits were pushed to this pull request.",
  "headStill": null
}
? 0
```

## Changed Files of the Rows a Reader Is Likely to Expand

The visible Pulls panel also names the changed files of the rows in view, once they have
stayed put for half a second, and of a row the pointer or focus rests on, at once and
first, up to the sixteen one ask names.
The server’s lane reads them one at a time behind the reader, so a row in view expanded
later draws its files from the cache at its first read, with no refresh asked and no
GitHub request, while a row out of view is still the reader’s own first read.
Below the budget’s floor the server refuses the first ask from memory and the panel asks
nothing more for a slow poll.
No list is asked for while GitHub reads the metadata of the rows in view, or while the
answer that says whether it does is still on its way, nor during a walk, and a prefetch
the server has not answered holds up none of the reader’s reads.
A files ask made while another prefetch is on its way waits for its answer and is
checked again when that answer comes, so a walk, a metadata read, or a hold that began
meanwhile keeps it from being sent.

This browserless session runs the production panel and file-tree controllers on a
virtual clock against a stand-in server whose GitHub list takes 1.5 s.

```console
$ node tests/dom/github-pulls-files-prefetch-behavior.js
{
  "asksBeforeDwell": 0,
  "visibleAsk": {
    "afterMs": 500,
    "files": [
      105,
      106,
      104,
      103,
      102,
      101,
      100,
      99,
      98,
      97,
      96,
      95,
      94,
      93,
      92,
      91
    ]
  },
  "restedAsk": {
    "afterMs": 0,
    "first": 89
  },
  "listed": [
    "105 by prefetch",
    "106 by prefetch",
    "104 by prefetch",
    "89 by prefetch",
    "103 by prefetch",
    "102 by prefetch",
    "101 by prefetch",
    "100 by prefetch",
    "99 by prefetch",
    "98 by prefetch",
    "97 by prefetch",
    "96 by prefetch",
    "95 by prefetch",
    "94 by prefetch",
    "93 by prefetch",
    "92 by prefetch"
  ],
  "expandedAfterPrefetch": {
    "drawnAfterMs": 0,
    "rows": 4,
    "refreshAsks": 0,
    "githubReads": []
  },
  "expandedOutOfView": {
    "drawnAfterMs": 2000,
    "rows": 4,
    "refreshAsks": 1,
    "githubReads": [
      "reader"
    ]
  },
  "belowFloor": {
    "asks": 1,
    "githubReads": 0
  },
  "afterFloor": {
    "asks": 1,
    "firstRead": 97
  },
  "behindMetadata": {
    "metadataSettledMs": 5000,
    "filesAskedMs": 5500,
    "listsBeforeSettled": 0
  },
  "asksDuringWalk": 0,
  "asksOnceStopped": 1,
  "readerReadsWhileAskHeld": [
    "pull-files +0 ms",
    "pull +0 ms"
  ],
  "pendingThenWalk": {
    "sentWhile": 0,
    "sentAfter": 1
  },
  "pendingThenMetadata": {
    "sentWhile": 0,
    "sentAfter": 1
  },
  "pendingThenDeferred": {
    "sentWhile": 0,
    "sentAfter": 0
  },
  "admissionHeld": {
    "asks": 0
  },
  "admissionAnswered": {
    "askedAfterMs": 3000,
    "first": 104
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
