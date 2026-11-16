---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Comparison Read Before Changes Asks

The pull-request page knows the comparison the moment its record arrives.
Its header’s Diff summary is drawn from it on every tab, and a reader on Conversation
often asks for Changes next.
So on every tab but Changes the prefetch reads it when the browser is idle, tells the
page what it read, and hands it to the diff when the tab is clicked.
This browserless session runs the production
`builtin_plugins/github/comparison-prefetch.js` as the page does: `want` on each paint
of every tab but Changes, `take` when a diff mounts, and `dispose` when the page goes.

Each step prints what has been asked of the server, what is held, and what a mount is
handed. A mount that finds nothing held or on its way reads the comparison then, through
the keep, as a page opened on Changes does, so its next visit is drawn from the keep.
A mount handed nothing, because that read failed, asks for itself and reports its own
errors. `summarized` is each answer the page was told of, for its Diff summary, and
`failedTold` each read no mount took that failed, which leaves the summary’s row empty
rather than holding its pending placeholder, and not standing for another comparison;
such a read is asked for again at the next paint.
A cancelled request, and one a mount took, tell the page nothing.
The session asserts, and so prints nothing for, that a poll of the same record sends
nothing, that a mount waiting through a dispose is let go, that a cancelled request
tells no failure, and that a disposed prefetch does nothing.

What a page reads is kept for the document, not for the page, since a page is mounted
again on every visit (mb-neg9). The later steps share one keep between pages: a second
visit to a comparison draws its Diff summary in the paint that shows its record, with no
request and no wait for idle, whether the first visit read it on Conversation or on
Changes, and a second page joins a request already on its way, including in the task
between an answer and its measurement.
A request is abandoned once every asker has gone, a mount taken while its page waited
for idle among them.
A record whose head moved names another comparison, which is read anew.
The keep is bounded by its answers’ JSON length, the oldest out first.
Last, the Pulls tab’s warmer reads the records of the pull requests a reader is likely
to open next, one at a time when the browser is idle, and asks only for a comparison the
keep has neither kept nor on its way.
Each warm counts against the hourly cap before its record is read, and each outcome
holds for the record’s freshness window, so a record that names no comparison, a
refusal, and an answer too large to keep are read once, not on every ask; an empty ask
empties the queue. The session asserts that a second visit, and a visit to a warmed
comparison, send no request.

```console
$ node tests/dom/github-pull-prefetch-session.js
{
  "steps": [
    {
      "step": "the record names a comparison: nothing is sent until the browser is idle",
      "phase": "waiting",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [],
      "assetsWarmed": 0,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "idle: one request, and the diff's assets",
      "phase": "fetching",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "the answer arrives and is held",
      "phase": "held",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ],
      "failedTold": []
    },
    {
      "step": "the reader clicks Files changed: it is handed over",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ],
      "failedTold": [],
      "handed": {
        "document": "first"
      }
    },
    {
      "step": "a later mount is handed it again, from the keep, with no request",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ],
      "failedTold": [],
      "handed": {
        "document": "first"
      }
    },
    {
      "step": "back on Conversation: nothing more is sent for that comparison",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ],
      "failedTold": []
    },
    {
      "step": "a click while the request is on its way waits for that request",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "it arrives",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ],
      "failedTold": [],
      "handed": {
        "document": "first"
      }
    },
    {
      "step": "a click before the browser was idle: the comparison is read now, through the keep, and only once",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 0,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "it arrives and the diff is handed it",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 0,
      "summarized": [],
      "failedTold": [],
      "handed": {
        "document": "first"
      }
    },
    {
      "step": "a page opened on Changes reads its comparison through the keep, and a later Conversation sends nothing more",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 0,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "it arrives and the diff is handed it",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 0,
      "summarized": [],
      "failedTold": [],
      "handed": {
        "document": "first"
      }
    },
    {
      "step": "a refreshed record moved the head: the old request is cancelled",
      "phase": "waiting",
      "comparison": "aaaa...cccc",
      "holding": false,
      "requests": [
        "bbbb (cancelled)"
      ],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "the new comparison is fetched",
      "phase": "fetching",
      "comparison": "aaaa...cccc",
      "holding": true,
      "requests": [
        "bbbb (cancelled)",
        "cccc"
      ],
      "assetsWarmed": 2,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "a mount is waiting on the old request: it is not cancelled",
      "phase": "waiting",
      "comparison": "aaaa...cccc",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "a refused request is not an error: the page is told, and the diff asks and says why",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": [
        "bbbb"
      ],
      "handed": null
    },
    {
      "step": "a refused request is asked again at the page's next paint",
      "phase": "held",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [
        "bbbb",
        "bbbb"
      ],
      "assetsWarmed": 2,
      "summarized": [
        "bbbb"
      ],
      "failedTold": [
        "bbbb"
      ]
    },
    {
      "step": "a request a mount took fails: the diff asks and says why, and the page is told nothing",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "a tab in the background sends nothing",
      "phase": "none",
      "comparison": null,
      "holding": false,
      "requests": [],
      "assetsWarmed": 0,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "the same page once it is shown",
      "phase": "fetching",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "the page goes: its request is cancelled and nothing is held",
      "phase": "none",
      "comparison": null,
      "holding": false,
      "requests": [
        "bbbb (cancelled)"
      ],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "the same endpoints at a changed route fetch again",
      "phase": "fetching",
      "comparison": "/api/plugin/github/pull-comparison?store=new",
      "holding": true,
      "requests": [
        "bbbb (cancelled)",
        "bbbb"
      ],
      "assetsWarmed": 2,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "the reader opens a pull request and leaves it: its answer stays in the keep",
      "phase": "none",
      "comparison": null,
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ],
      "failedTold": [],
      "kept": [
        "aaaa...bbbb"
      ]
    },
    {
      "step": "another pull request's page reads its own comparison",
      "phase": "fetching",
      "comparison": "aaaa...cccc",
      "holding": true,
      "requests": [
        "cccc"
      ],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "the first pull request again: its summary is drawn in the paint that shows the record, with no request and no wait",
      "phase": "held",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ],
      "failedTold": [],
      "waitingForIdle": 0
    },
    {
      "step": "its Changes is handed the same answer",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ],
      "failedTold": [],
      "handed": {
        "document": "first"
      }
    },
    {
      "step": "a pull request first opened on Changes, opened again on Conversation: drawn from the keep, with no request and no wait",
      "phase": "held",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ],
      "failedTold": [],
      "waitingForIdle": 0,
      "kept": [
        "aaaa...bbbb"
      ]
    },
    {
      "step": "a page behind another tab draws a kept summary too: it costs nothing",
      "phase": "held",
      "comparison": "aaaa...cccc",
      "holding": true,
      "requests": [],
      "assetsWarmed": 1,
      "summarized": [
        "cccc"
      ],
      "failedTold": []
    },
    {
      "step": "the head moved: the record names another comparison, which is read, and the old one is not drawn",
      "phase": "fetching",
      "comparison": "aaaa...dddd",
      "holding": true,
      "requests": [
        "dddd"
      ],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": []
    },
    {
      "step": "a second page while the first's request is on its way joins it, and sends nothing",
      "phase": "fetching",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": [],
      "firstPageRequests": 1
    },
    {
      "step": "the first page went; the request it shared answers the second",
      "phase": "held",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ],
      "failedTold": []
    },
    {
      "step": "an answer arrived and is not yet measured: a visit then joins its request, and sends none",
      "phase": "fetching",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [],
      "assetsWarmed": 1,
      "summarized": [],
      "failedTold": [],
      "keep": {
        "kept": [],
        "chars": 0,
        "pending": [
          "aaaa...bbbb"
        ]
      }
    },
    {
      "step": "a task later it is measured and kept; the visit that joined is drawn from it",
      "phase": "held",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ],
      "failedTold": [],
      "keep": {
        "kept": [
          "aaaa...bbbb"
        ],
        "chars": 20,
        "pending": []
      }
    },
    {
      "step": "a page waiting for idle is taken while a warm of its comparison is on its way; the warmer and the page go: the request is abandoned",
      "warmRequests": 1,
      "sharedRequestAborted": true,
      "pending": []
    },
    {
      "step": "a keep of 70 characters of JSON, 40 for one answer: the oldest answer goes first, and a larger one is not kept",
      "keep": {
        "kept": [
          "aaaa...b2",
          "aaaa...b3"
        ],
        "chars": 64,
        "pending": []
      }
    },
    {
      "step": "the Pulls tab names six pull requests: five are queued, and nothing is read until idle",
      "queue": [
        8,
        10,
        11,
        12,
        13
      ],
      "running": null,
      "sentThisHour": 0,
      "recent": [],
      "recordReads": [],
      "comparisonRequests": [],
      "kept": []
    },
    {
      "step": "idle: the first one's record is read from the cache",
      "queue": [
        10,
        11,
        12,
        13
      ],
      "running": 8,
      "sentThisHour": 1,
      "recent": [],
      "recordReads": [
        "8"
      ],
      "comparisonRequests": [],
      "kept": []
    },
    {
      "step": "its record names a comparison the keep lacks: it is asked for",
      "queue": [
        10,
        11,
        12,
        13
      ],
      "running": 8,
      "sentThisHour": 1,
      "recent": [],
      "recordReads": [
        "8"
      ],
      "comparisonRequests": [
        "head8"
      ],
      "kept": []
    },
    {
      "step": "it is kept, and at the next idle the second's record is read",
      "queue": [
        11,
        12,
        13
      ],
      "running": 10,
      "sentThisHour": 2,
      "recent": [
        "8: warmed"
      ],
      "recordReads": [
        "8",
        "10"
      ],
      "comparisonRequests": [
        "head8"
      ],
      "kept": [
        "/api/plugin/github/pull-comparison?number=8"
      ]
    },
    {
      "step": "the reader opens the first: its page draws the summary with no request",
      "phase": "held",
      "comparison": "/api/plugin/github/pull-comparison?number=8",
      "holding": true,
      "requests": [],
      "assetsWarmed": 1,
      "summarized": [
        "head8"
      ],
      "failedTold": []
    },
    {
      "step": "the reader rests on another row: the queue is replaced, the one being read goes on, and the kept one is not looked up again",
      "queue": [
        11
      ],
      "running": 10,
      "sentThisHour": 2,
      "recent": [
        "8: warmed"
      ],
      "recordReads": [
        "8",
        "10"
      ],
      "comparisonRequests": [
        "head8"
      ],
      "kept": [
        "/api/plugin/github/pull-comparison?number=8"
      ]
    },
    {
      "step": "the one being read is kept, and a record with no comparison is passed over",
      "queue": [],
      "running": null,
      "sentThisHour": 3,
      "recent": [
        "8: warmed",
        "10: warmed",
        "11: no comparison"
      ],
      "recordReads": [
        "8",
        "10",
        "11"
      ],
      "comparisonRequests": [
        "head8",
        "head10"
      ],
      "kept": [
        "/api/plugin/github/pull-comparison?number=8",
        "/api/plugin/github/pull-comparison?number=10"
      ]
    },
    {
      "step": "asked again within the window, the record with no comparison is not read again",
      "queue": [],
      "running": null,
      "sentThisHour": 3,
      "recent": [
        "8: warmed",
        "10: warmed",
        "11: no comparison"
      ],
      "recordReads": [
        "8",
        "10",
        "11"
      ],
      "comparisonRequests": [
        "head8",
        "head10"
      ],
      "kept": [
        "/api/plugin/github/pull-comparison?number=8",
        "/api/plugin/github/pull-comparison?number=10"
      ]
    },
    {
      "step": "past the record's freshness window it is read again, and the keep answers: no request",
      "queue": [],
      "running": null,
      "sentThisHour": 4,
      "recent": [
        "8: warmed",
        "10: warmed",
        "11: no comparison",
        "8: kept"
      ],
      "recordReads": [
        "8",
        "10",
        "11",
        "8"
      ],
      "comparisonRequests": [
        "head8",
        "head10"
      ],
      "kept": [
        "/api/plugin/github/pull-comparison?number=8",
        "/api/plugin/github/pull-comparison?number=10"
      ]
    },
    {
      "step": "an empty ask, as a panel hidden, parked, or offline makes, empties the queue",
      "queue": [],
      "running": null,
      "sentThisHour": 4,
      "recent": [
        "8: warmed",
        "10: warmed",
        "11: no comparison",
        "8: kept"
      ],
      "recordReads": [
        "8",
        "10",
        "11",
        "8"
      ],
      "comparisonRequests": [
        "head8",
        "head10"
      ],
      "kept": [
        "/api/plugin/github/pull-comparison?number=8",
        "/api/plugin/github/pull-comparison?number=10"
      ]
    },
    {
      "step": "a warm whose record is read while the open page's comparison is on its way waits for it",
      "pageRequests": 1,
      "warmRequests": []
    },
    {
      "step": "the page's answer arrives: the warm is sent",
      "warmRequests": [
        "head20"
      ]
    },
    {
      "step": "ten asks a second apart, each naming the same three pull requests: each is read once, whatever its outcome",
      "answersKept": {
        "recordReads": 3,
        "comparisonRequests": 3,
        "kept": [
          "base...head31",
          "base...head32",
          "base...head33"
        ],
        "recent": [
          "31: warmed",
          "32: warmed",
          "33: warmed"
        ]
      },
      "noComparison": {
        "recordReads": 3,
        "comparisonRequests": 0,
        "kept": [],
        "recent": [
          "31: no comparison",
          "32: no comparison",
          "33: no comparison"
        ]
      },
      "refused": {
        "recordReads": 3,
        "comparisonRequests": 3,
        "kept": [],
        "recent": [
          "31: failed",
          "32: failed",
          "33: failed"
        ]
      },
      "tooLargeToKeep": {
        "recordReads": 3,
        "comparisonRequests": 3,
        "kept": [],
        "recent": [
          "31: not kept",
          "32: not kept",
          "33: not kept"
        ]
      }
    }
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
