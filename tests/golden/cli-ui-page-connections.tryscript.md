---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Page’s Connections Across the Back/Forward Cache

A browser keeps a page it may show again on Back, with its heap and its open requests,
and opens six connections to a host.
Each kept page’s event stream held one of them, so after five page loads in one tab the
next page’s requests waited for a connection, up to a minute
(`explorations/page-connections/README.md`). The shell now parks its connections on a
`pagehide` that says the page is kept, and reopens them on the `pageshow` that brings it
back.

This browserless session runs that decision, `createPageConnections` in
`static/navigation.js`, with the declarations of `static/app.js` it decides about
extracted verbatim: the inventory event stream with its reconnect and stable-connection
timers, the live tail of a log, and the `pagehide` and `pageshow` listeners.
The catalog feed the stream starts when it opens is the production module.
Only the browser is a double: `EventSource`, the timers, and `fetch` record what they
are asked.

Each step lists what the page `did`, in order, and what it holds `after`: its open
streams, its pending timers, and how many connections are parked.
The transcript pins five things:

- A kept page closes its event stream and cancels the stream’s timers, so it holds no
  connection. A restore opens one new stream, which begins with a snapshot and one
  catalog request, as a reconnect does.
  A second `pageshow` with nothing parked opens nothing, and a page can be kept and
  restored again.
- A page kept while its stream waits to reconnect cancels that reconnect, and a restore
  opens one stream at once instead of two.
- A live log’s tail is closed with the event stream and reopened from the byte it had
  reached.
- A pin has no stream: nothing is parked, and a restore opens and requests nothing.
- A `pagehide` that does not keep the page tears the keyboard and Quick File down, as
  before, and closes nothing.
  Every restore rebuilds them first, whether or not a teardown removed them.

```console
$ node tests/dom/page-connections-session.js
[
  {
    "scenario": "a folder's page is kept for Back and restored",
    "steps": [
      {
        "step": "the page starts",
        "did": [
          "stream 1: opened /api/events?scope=root-depth-2"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [],
          "parked": 0
        }
      },
      {
        "step": "stream 1 opens and sends its snapshot",
        "did": [
          "timer 1: set for 10000 ms",
          "request: GET /api/catalog",
          "tree: snapshot of 1 entries applied"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0
        }
      },
      {
        "step": "pagehide, kept for Back",
        "did": [
          "timer 1: cancelled",
          "stream 1: closed"
        ],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 1
        }
      },
      {
        "step": "pageshow, restored",
        "did": [
          "page: keyboard rebuilt if torn down",
          "page: Quick File rebuilt if torn down",
          "stream 2: opened /api/events?scope=root-depth-2"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [],
          "parked": 0
        }
      },
      {
        "step": "stream 2 opens and sends its snapshot",
        "did": [
          "timer 2: set for 10000 ms",
          "request: GET /api/catalog",
          "tree: snapshot of 1 entries applied"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0
        }
      },
      {
        "step": "a file changes",
        "did": [
          "tree: 1 change applied"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0
        }
      },
      {
        "step": "pageshow, restored, with no pagehide before it",
        "did": [
          "page: keyboard rebuilt if torn down",
          "page: Quick File rebuilt if torn down"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0
        }
      },
      {
        "step": "pagehide, kept for Back again",
        "did": [
          "timer 2: cancelled",
          "stream 2: closed"
        ],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 1
        }
      },
      {
        "step": "pageshow, restored again",
        "did": [
          "page: keyboard rebuilt if torn down",
          "page: Quick File rebuilt if torn down",
          "stream 3: opened /api/events?scope=root-depth-2"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [],
          "parked": 0
        }
      }
    ]
  },
  {
    "scenario": "a page is kept for Back while its stream waits to reconnect",
    "steps": [
      {
        "step": "the page starts and stream 1 opens",
        "did": [
          "stream 1: opened /api/events?scope=root-depth-2",
          "timer 1: set for 10000 ms",
          "request: GET /api/catalog"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0
        }
      },
      {
        "step": "stream 1 fails five times",
        "did": [
          "timer 1: cancelled",
          "stream 1: closed",
          "timer 2: set for 2000 ms"
        ],
        "after": {
          "streams": [],
          "timers": [
            "2000 ms"
          ],
          "parked": 0
        }
      },
      {
        "step": "pagehide, kept for Back",
        "did": [
          "timer 2: cancelled"
        ],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 1
        }
      },
      {
        "step": "pageshow, restored",
        "did": [
          "page: keyboard rebuilt if torn down",
          "page: Quick File rebuilt if torn down",
          "stream 2: opened /api/events?scope=root-depth-2"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [],
          "parked": 0
        }
      }
    ]
  },
  {
    "scenario": "a page tailing a live log is kept for Back and restored",
    "steps": [
      {
        "step": "the page starts and stream 1 opens",
        "did": [
          "stream 1: opened /api/events?scope=root-depth-2",
          "timer 1: set for 10000 ms",
          "request: GET /api/catalog"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0
        }
      },
      {
        "step": "a live log is opened, read to byte 120",
        "did": [
          "stream 2: opened /api/stream?path=run.jsonl&cursor=120"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2",
            "/api/stream?path=run.jsonl&cursor=120"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0
        }
      },
      {
        "step": "the log grows to byte 300",
        "did": [],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2",
            "/api/stream?path=run.jsonl&cursor=120"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0
        }
      },
      {
        "step": "pagehide, kept for Back",
        "did": [
          "timer 1: cancelled",
          "stream 1: closed",
          "stream 2: closed"
        ],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 2
        }
      },
      {
        "step": "pageshow, restored",
        "did": [
          "page: keyboard rebuilt if torn down",
          "page: Quick File rebuilt if torn down",
          "stream 3: opened /api/events?scope=root-depth-2",
          "stream 4: opened /api/stream?path=run.jsonl&cursor=300"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2",
            "/api/stream?path=run.jsonl&cursor=300"
          ],
          "timers": [],
          "parked": 0
        }
      }
    ]
  },
  {
    "scenario": "a pin's page is kept for Back and restored",
    "steps": [
      {
        "step": "the page starts",
        "did": [
          "request: GET /api/catalog"
        ],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 0
        }
      },
      {
        "step": "pagehide, kept for Back",
        "did": [],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 0
        }
      },
      {
        "step": "pageshow, restored",
        "did": [
          "page: keyboard rebuilt if torn down",
          "page: Quick File rebuilt if torn down"
        ],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 0
        }
      }
    ]
  },
  {
    "scenario": "a page is unloaded",
    "steps": [
      {
        "step": "pageshow, the first load",
        "did": [],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 0
        }
      },
      {
        "step": "the page starts and stream 1 opens",
        "did": [
          "stream 1: opened /api/events?scope=root-depth-2",
          "timer 1: set for 10000 ms",
          "request: GET /api/catalog"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0
        }
      },
      {
        "step": "pagehide, not kept",
        "did": [
          "page: keyboard and Quick File torn down"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0
        }
      },
      {
        "step": "pageshow, restored all the same",
        "did": [
          "page: keyboard rebuilt if torn down",
          "page: Quick File rebuilt if torn down"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0
        }
      }
    ]
  }
]
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
