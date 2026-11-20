---
cwd: ../..
sandbox: false
---
# Golden Test: What a Page Reports to the Event Log, and Its Details

The owner asked, 2026-11-19, that a Diff summary still loading after many seconds be
captured, surfaced, and easy to debug (mb-9zp5). `static/event-reports.js` is the page’s
side of the event log: it names each request the page sends to its own server’s `/api/`
with the page’s client ID, and reports to `POST /api/event-log/client` what only the
page saw. Its Details panel reads the event log back for a failure or a late wait.

This browserless session runs the production file whole, with the clock, timers, fetch,
and paint injected, and tells what the reporter queued and sent at each step.
The settings are the ones the shell serves with a log open;
`tests/test_event_reports_session.py` fails when they differ, checks that the route
accepts every body sent here whole, and runs the Details on the routes’ real answers for
a refresh job that never ends.
The transcript pins these behaviors:

- A request to the page’s own `/api/` carries `x-metabrowser-client: <page>-<n>`; a
  static asset, another origin, a long-lived stream, the reports themselves, and every
  request when the server writes no log carry nothing, and their requests are the
  caller’s, untouched.
- A request answered under `slow_ms` (2 s) reports nothing.
  One still pending at 2 s is reported `open`; its end is reported with its status, the
  `srv` duration of its Server-Timing, and an outcome: `failed` for a network error or a
  5xx, `cancelled` for an abort, `ok` otherwise.
  One reported open and still pending when the page is left ends `never_completed`.
- A wait the page shows as loading reports nothing if it ends before `late_ms` (10 s).
  Still running at 10 s, timed from when it began even if the reporter was loaded later,
  it is reported `open` and the page is told, then its end is reported once; a page left
  first ends it `never_completed`.
- A frame that blocked the page for `freeze_ms` (500 ms) or more is reported with the
  function, source path, and invoker the browser blamed; requests answered before the
  reporter loaded are read from Resource Timing.
- Reports leave in one body per second, or at once at 20; past 30 a minute the page
  drops them and says how many in its next body.
- The shell’s install wraps `window.fetch`, observes long animation frames, flushes when
  the page is hidden and ends what is late when it is left, and sends each body with
  `keepalive`, same-origin credentials, and the JSON type the same-origin guard
  requires. With no log it leaves `window.fetch` alone and still says when a wait is
  late.
- The Details list what the server is still running (this page’s first), the failures in
  the window by cause with their message, addresses, and latest calls, the last probe of
  GitHub, and this page’s own slow, failed, or unfinished records, with links to both
  answers as JSON. They say plainly when the log is off, when neither route answered,
  and when nothing is on record; a panel closed before its answers arrive is left as it
  was.

```console
$ node tests/dom/event-reports-session.js
{
  "settings": {
    "log": true,
    "off_reason": null,
    "route": "/api/event-log/client",
    "header": "x-metabrowser-client",
    "slow_ms": 2000,
    "freeze_ms": 500,
    "late_ms": 10000,
    "flush_ms": 1000,
    "max_batch": 20,
    "per_minute": 30,
    "long_lived": [
      "/api/events",
      "/api/tail",
      "/api/stream"
    ],
    "failure_window_s": 3600
  },
  "tags": {
    "a read of a pull request": "k3v9q2zx-1 GET /api/plugin/github/pull",
    "a refresh it asks for": "k3v9q2zx-2 POST /api/plugin/github/pull-refresh",
    "a static asset": "untagged",
    "another origin": "untagged",
    "the server's event stream": "untagged",
    "a live tail": "untagged",
    "the reports themselves": "untagged",
    "with no log on the server": "untagged"
  },
  "wrapFetch": {
    "a tagged request's headers": {
      "accept": "application/json",
      "x-metabrowser-client": "k3v9q2zx-1"
    },
    "a tagged request's init is a copy": true,
    "an untagged request's init is the caller's": true,
    "a no-cors request is untagged": true,
    "a fast answer queues nothing": 0
  },
  "requests": {
    "steps": [
      {
        "step": "a request answered in 150 ms",
        "queued": [],
        "timers": 0
      },
      {
        "step": "a request 1999 ms on its way",
        "queued": [],
        "timers": 1
      },
      {
        "step": "the same at 2000 ms: still pending, reported open",
        "queued": [
          "fetch open GET /api/plugin/github/pull-files-summary k3v9q2zx-2 2000 ms {\"threshold_ms\":2000}"
        ],
        "timers": 1
      },
      {
        "step": "it answers at 2500 ms, with its Server-Timing",
        "queued": [
          "fetch open GET /api/plugin/github/pull-files-summary k3v9q2zx-2 2000 ms {\"threshold_ms\":2000}",
          "fetch end GET /api/plugin/github/pull-files-summary k3v9q2zx-2 2500 ms ok {\"status\":200,\"threshold_ms\":2000,\"server_ms\":2301.2}"
        ],
        "timers": 1
      },
      {
        "step": "a second later, the batch sent",
        "queued": [],
        "timers": 0
      },
      {
        "step": "one that failed on the network, after 2600 ms",
        "queued": [
          "fetch open GET /api/plugin/github/pull k3v9q2zx-3 2000 ms {\"threshold_ms\":2000}",
          "fetch end GET /api/plugin/github/pull k3v9q2zx-3 2600 ms failed {\"status\":0,\"threshold_ms\":2000,\"error\":\"TypeError\"}"
        ],
        "timers": 1
      },
      {
        "step": "one the page aborted, after 2600 ms",
        "queued": [
          "fetch open GET /api/plugin/github/pull k3v9q2zx-4 2000 ms {\"threshold_ms\":2000}",
          "fetch end GET /api/plugin/github/pull k3v9q2zx-4 2600 ms cancelled {\"status\":0,\"threshold_ms\":2000,\"error\":\"AbortError\"}"
        ],
        "timers": 1
      },
      {
        "step": "one the server answered 503, after 2600 ms",
        "queued": [
          "fetch open GET /api/plugin/github/pull k3v9q2zx-5 2000 ms {\"threshold_ms\":2000}",
          "fetch end GET /api/plugin/github/pull k3v9q2zx-5 2600 ms failed {\"status\":503,\"threshold_ms\":2000}"
        ],
        "timers": 1
      },
      {
        "step": "one the server answered 404, after 2600 ms",
        "queued": [
          "fetch open GET /api/plugin/github/pull k3v9q2zx-6 2000 ms {\"threshold_ms\":2000}",
          "fetch end GET /api/plugin/github/pull k3v9q2zx-6 2600 ms ok {\"status\":404,\"threshold_ms\":2000}"
        ],
        "timers": 1
      },
      {
        "step": "one pending 4.1 s, another 100 ms",
        "queued": [],
        "timers": 1
      },
      {
        "step": "the page is left: the one reported open never completed, the other is let go",
        "queued": [],
        "timers": 0
      }
    ],
    "sent": [
      {
        "to": "/api/event-log/client",
        "at_ms": 3150,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "fetch open GET /api/plugin/github/pull-files-summary k3v9q2zx-2 2000 ms {\"threshold_ms\":2000}",
          "fetch end GET /api/plugin/github/pull-files-summary k3v9q2zx-2 2500 ms ok {\"status\":200,\"threshold_ms\":2000,\"server_ms\":2301.2}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 6650,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "fetch open GET /api/plugin/github/pull k3v9q2zx-3 2000 ms {\"threshold_ms\":2000}",
          "fetch end GET /api/plugin/github/pull k3v9q2zx-3 2600 ms failed {\"status\":0,\"threshold_ms\":2000,\"error\":\"TypeError\"}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 9250,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "fetch open GET /api/plugin/github/pull k3v9q2zx-4 2000 ms {\"threshold_ms\":2000}",
          "fetch end GET /api/plugin/github/pull k3v9q2zx-4 2600 ms cancelled {\"status\":0,\"threshold_ms\":2000,\"error\":\"AbortError\"}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 11850,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "fetch open GET /api/plugin/github/pull k3v9q2zx-5 2000 ms {\"threshold_ms\":2000}",
          "fetch end GET /api/plugin/github/pull k3v9q2zx-5 2600 ms failed {\"status\":503,\"threshold_ms\":2000}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 14450,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "fetch open GET /api/plugin/github/pull k3v9q2zx-6 2000 ms {\"threshold_ms\":2000}",
          "fetch end GET /api/plugin/github/pull k3v9q2zx-6 2600 ms ok {\"status\":404,\"threshold_ms\":2000}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 17050,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "fetch open GET /api/plugin/github/pull-comparison k3v9q2zx-7 2000 ms {\"threshold_ms\":2000}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 18150,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "fetch end GET /api/plugin/github/pull-comparison k3v9q2zx-7 4100 ms never_completed {\"threshold_ms\":2000}"
        ]
      }
    ]
  },
  "waits": {
    "steps": [
      {
        "step": "a wait that ends at 9999 ms",
        "queued": [],
        "late_told": []
      },
      {
        "step": "a wait still running at 10 s",
        "queued": [
          "wait open githubPull:diffSummary k3v9q2zx 10000 ms {\"threshold_ms\":10000,\"detail\":{\"number\":7}}"
        ],
        "late_told": [
          "told late at 10000 ms"
        ]
      },
      {
        "step": "it ends at 12.5 s, and once only",
        "queued": [
          "wait end githubPull:diffSummary k3v9q2zx 12500 ms ok {\"threshold_ms\":10000,\"detail\":{\"number\":7}}"
        ],
        "late_told": [
          "told late at 10000 ms"
        ]
      },
      {
        "step": "a wait begun 4 s before it was named, 5999 ms after",
        "queued": [],
        "late_told": [
          "told late at 10000 ms"
        ]
      },
      {
        "step": "6 s after it was named, 10 s after it began",
        "queued": [
          "wait open source:refresh k3v9q2zx 10000 ms {\"threshold_ms\":10000}"
        ],
        "late_told": [
          "told late at 10000 ms"
        ]
      },
      {
        "step": "a wait whose late handler throws is still reported",
        "queued": [
          "wait open githubPull:refresh k3v9q2zx 10000 ms {\"threshold_ms\":10000}"
        ],
        "late_told": [
          "told late at 10000 ms"
        ]
      },
      {
        "step": "the page is left: the late waits never completed",
        "queued": [],
        "late_told": [
          "told late at 10000 ms"
        ]
      },
      {
        "step": "ending them after that reports nothing more",
        "queued": [],
        "late_told": [
          "told late at 10000 ms"
        ]
      }
    ],
    "sent": [
      {
        "to": "/api/event-log/client",
        "at_ms": 20999,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "wait open githubPull:diffSummary k3v9q2zx 10000 ms {\"threshold_ms\":10000,\"detail\":{\"number\":7}}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 23499,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "wait end githubPull:diffSummary k3v9q2zx 12500 ms ok {\"threshold_ms\":10000,\"detail\":{\"number\":7}}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 29499,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "wait open source:refresh k3v9q2zx 10000 ms {\"threshold_ms\":10000}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 38499,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "wait open githubPull:refresh k3v9q2zx 10000 ms {\"threshold_ms\":10000}",
          "wait end source:refresh k3v9q2zx 20000 ms never_completed {\"threshold_ms\":10000}",
          "wait end githubPull:refresh k3v9q2zx 10000 ms never_completed {\"threshold_ms\":10000}"
        ]
      }
    ]
  },
  "hiddenTab": {
    "steps": [
      {
        "step": "shown 4 s, then hidden a minute: not late",
        "queued": [],
        "late_told": []
      },
      {
        "step": "shown again 5999 ms: 9999 ms shown in all",
        "queued": [],
        "late_told": []
      },
      {
        "step": "10 s shown: late, with the minute it was hidden",
        "queued": [
          "wait open githubPull:diffSummary k3v9q2zx 70000 ms {\"threshold_ms\":10000,\"hidden\":true,\"hidden_ms\":60000,\"detail\":{\"number\":7}}"
        ],
        "late_told": [
          "told late at 70000 ms"
        ]
      },
      {
        "step": "it ends a second later",
        "queued": [
          "wait end githubPull:diffSummary k3v9q2zx 71000 ms ok {\"threshold_ms\":10000,\"hidden\":true,\"hidden_ms\":60000,\"detail\":{\"number\":7}}"
        ],
        "late_told": [
          "told late at 70000 ms"
        ]
      },
      {
        "step": "a wait begun while hidden, 30 s on: not late",
        "queued": [],
        "late_told": [
          "told late at 70000 ms"
        ]
      },
      {
        "step": "shown for the late threshold: late",
        "queued": [
          "wait open source:refresh k3v9q2zx 40000 ms {\"threshold_ms\":10000,\"hidden\":true,\"hidden_ms\":30000}"
        ],
        "late_told": [
          "told late at 70000 ms"
        ]
      },
      {
        "step": "hidden 5 s more, then left: never completed, hidden 35 s",
        "queued": [],
        "late_told": [
          "told late at 70000 ms"
        ]
      }
    ],
    "sent": [
      {
        "to": "/api/event-log/client",
        "at_ms": 71000,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "wait open githubPull:diffSummary k3v9q2zx 70000 ms {\"threshold_ms\":10000,\"hidden\":true,\"hidden_ms\":60000,\"detail\":{\"number\":7}}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 72000,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "wait end githubPull:diffSummary k3v9q2zx 71000 ms ok {\"threshold_ms\":10000,\"hidden\":true,\"hidden_ms\":60000,\"detail\":{\"number\":7}}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 112000,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "wait open source:refresh k3v9q2zx 40000 ms {\"threshold_ms\":10000,\"hidden\":true,\"hidden_ms\":30000}"
        ]
      },
      {
        "to": "/api/event-log/client",
        "at_ms": 116000,
        "page": "k3v9q2zx",
        "path": "/pull/7",
        "dropped": 0,
        "reports": [
          "wait end source:refresh k3v9q2zx 45000 ms never_completed {\"threshold_ms\":10000,\"hidden\":true,\"hidden_ms\":35000}"
        ]
      }
    ]
  },
  "blockedAndEarlier": [
    {
      "to": "/api/event-log/client",
      "at_ms": 1000,
      "page": "k3v9q2zx",
      "path": "/pull/7",
      "dropped": 0,
      "reports": [
        "render end blocked k3v9q2zx 812.4 ms ok {\"threshold_ms\":500,\"detail\":{\"at_ms\":4322,\"blocking_ms\":762,\"function\":\"paintSummaryWait\",\"source\":\"/static/plugins/github/pull-page.js\",\"invoker\":\"TimerHandler:setTimeout\"}}",
        "render end blocked k3v9q2zx 650 ms ok {\"threshold_ms\":500,\"detail\":{\"at_ms\":9000}}",
        "fetch end /api/plugin/github/pull k3v9q2zx 3210.6 ms ok {\"threshold_ms\":2000,\"detail\":{\"source\":\"resource_timing\"},\"status\":200,\"server_ms\":3190.1}",
        "fetch end /api/plugin/github/pulls k3v9q2zx 2000 ms ok {\"threshold_ms\":2000,\"detail\":{\"source\":\"resource_timing\"}}"
      ]
    }
  ],
  "batches": {
    "25 reports at once: bodies sent before the flush": 1,
    "their sizes": [
      20,
      5
    ],
    "10 more in the same minute: reports sent, and dropped": [
      5,
      5
    ],
    "the next minute: reports sent": [
      1
    ],
    "every body's largest size in bytes": 3010
  },
  "install": {
    "the SDK's eventReports": [
      "failureWindowS",
      "lateMs",
      "page",
      "showDetails",
      "wait"
    ],
    "its page": "eight letters and digits",
    "a request through window.fetch carries": [
      "x-metabrowser-client"
    ],
    "freezes observed": [
      {
        "type": "long-animation-frame",
        "buffered": true
      }
    ],
    "listens for": [
      "document visibilitychange",
      "pagehide"
    ],
    "batches sent by the time the page is hidden": 2,
    "reports are sent with": [
      {
        "method": "POST",
        "keepalive": true,
        "credentials": "same-origin",
        "type": "application/json"
      },
      {
        "method": "POST",
        "keepalive": true,
        "credentials": "same-origin",
        "type": "application/json"
      },
      {
        "method": "POST",
        "keepalive": true,
        "credentials": "same-origin",
        "type": "application/json"
      },
      {
        "method": "POST",
        "keepalive": true,
        "credentials": "same-origin",
        "type": "application/json"
      }
    ],
    "what was sent": [
      "fetch end /api/tree <page> 2500 ms ok {\"threshold_ms\":2000,\"detail\":{\"source\":\"resource_timing\"}}",
      "wait open githubPull:diffSummary <page> 10000 ms {\"threshold_ms\":10000,\"detail\":{\"number\":7}}",
      "render end blocked <page> 900 ms ok {\"threshold_ms\":500,\"detail\":{\"at_ms\":50}}",
      "wait end githubPull:diffSummary <page> 10000 ms ok {\"threshold_ms\":10000,\"detail\":{\"number\":7}}",
      "wait open githubPull:refresh <page> 10000 ms {\"threshold_ms\":10000}",
      "wait end githubPull:refresh <page> 10000 ms never_completed {\"threshold_ms\":10000}"
    ],
    "with no log, window.fetch is the page's own": true,
    "with no log, a wait still says it is late": true,
    "with no settings, nothing is installed": true
  },
  "details": {
    "routes": {
      "failures": "/api/event-log/failures?since=2026-11-19T21%3A00%3A00Z&until=2026-11-19T21%3A43%3A00Z",
      "page": "/api/event-log?client=k3v9q2zx&limit=200"
    },
    "a stuck job, GitHub unreachable, and this page's wait": [
      {
        "heading": "Still running",
        "items": [
          "checkout._pull_job · for 61.0 s",
          "gh api · for 9.0 s"
        ]
      },
      {
        "heading": "connect timeout: 3 in the window",
        "items": [
          "GitHub could not be reached because the connection to api.github.com at 20.172.24.160 timed out after 2 s; other sites are reachable",
          "Addresses: 20.172.24.160",
          "gh api · timeout · 15.0 s · <time>"
        ]
      },
      {
        "heading": "Probe of api.github.com:443: connect timeout",
        "items": [
          "20.172.24.160 · timeout · 2.0 s"
        ]
      },
      {
        "heading": "This page’s slow or unfinished work",
        "items": [
          "wait githubPull:diffSummary · never_completed · 61.2 s · <time>",
          "checkout._pull_job · still running · 32.0 s · <time>",
          "gh api · timeout · connect timeout · 15.0 s · <time>"
        ]
      }
    ],
    "the log off": [
      {
        "heading": "The event log is off on this server",
        "items": []
      }
    ],
    "neither route answered": [
      {
        "heading": "The event log could not be read",
        "items": []
      }
    ],
    "nothing on record": [
      {
        "heading": "Nothing slow or failed is on record for this",
        "items": []
      }
    ],
    "panel": {
      "while it reads": [
        "event-log-details-note: Reading the event log…"
      ],
      "asked": [
        {
          "route": "/api/event-log/failures?since=2026-11-19T21%3A00%3A00Z",
          "accept": "application/json",
          "signal": false
        },
        {
          "route": "/api/event-log?client=k3v9q2zx&limit=200",
          "accept": "application/json",
          "signal": false
        },
        {
          "route": "/api/event-log/failures",
          "accept": "application/json",
          "signal": true
        },
        {
          "route": "/api/event-log?client=k3v9q2zx&limit=200",
          "accept": "application/json",
          "signal": true
        }
      ],
      "painted": [
        "Still running",
        "  checkout._pull_job · for 61.0 s",
        "  gh api · for 9.0 s",
        "connect timeout: 3 in the window",
        "  GitHub could not be reached because the connection to api.github.com at 20.172.24.160 timed out after 2 s; other sites are reachable",
        "  Addresses: 20.172.24.160",
        "  gh api · timeout · 15.0 s · <time>",
        "Probe of api.github.com:443: connect timeout",
        "  20.172.24.160 · timeout · 2.0 s",
        "This page’s slow or unfinished work",
        "  wait githubPull:diffSummary · never_completed · 61.2 s · <time>",
        "  checkout._pull_job · still running · 32.0 s · <time>",
        "  gh api · timeout · connect timeout · 15.0 s · <time>",
        "links: Failures as JSON -> /api/event-log/failures?since=2026-11-19T21%3A00%3A00Z (_blank, noopener); This page’s records as JSON -> /api/event-log?client=k3v9q2zx&limit=200 (_blank, noopener)"
      ],
      "closed before the answers": [
        "event-log-details-note: Reading the event log…"
      ],
      "the routes unreachable, no page": [
        "The event log could not be read",
        "links: Failures as JSON -> /api/event-log/failures (_blank, noopener)"
      ],
      "the log off on this server": {
        "painted": [
          "The event log is off on this server",
          "  Nothing this server does is recorded, so there is nothing to show here."
        ],
        "asked": 0
      },
      "the log off with its reason": [
        "The event log is off on this server",
        "  Nothing this server does is recorded, so there is nothing to show here.",
        "  Why: the folder this server shows is the event log's own, and recording its requests would change the files on screen"
      ]
    }
  },
  "serverTiming": {
    "srv;dur=12.5": 12.5,
    "cache;desc=hit, srv;dur=7": 7,
    "app;dur=3": null,
    "(none)": null
  }
}
? 0
```
