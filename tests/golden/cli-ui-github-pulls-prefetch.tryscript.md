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

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
