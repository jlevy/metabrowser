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
The transcript pins these behaviors:

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
  A restore rebuilds them only if a teardown removed them.
- Each snapshot names its connection, first in the frame, so a snapshot that differs
  from the last only in its connection is still the same tree.
  The page’s file watches (`static/file-watches.js`, loaded when a view first watches a
  file) register on the connection the last snapshot named, with the generation the
  reader holds; a `file.changed` tells each watch’s listeners once.
  Every new connection, after a resync, a server restart, or a restore from Back,
  registers every watch again with the generation it holds, and the server’s answer
  tells a listener of a change it missed while no stream was open.
  A registration on a connection the server does not hold waits for the next snapshot,
  and a disposed watch is unregistered.

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
        "step": "a duplicate pagehide preserves the parked connections",
        "did": [],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 1
        }
      },
      {
        "step": "a late task cannot open an event stream while parked",
        "did": [],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 1
        }
      },
      {
        "step": "pageshow, restored",
        "did": [
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
          "event: metabrowser:inventory-change snapshot anything may have changed"
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
        "did": [],
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
          "stream 3: opened /api/events?scope=root-depth-2"
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
        "step": "stream 3 sends the original snapshot after a change was undone",
        "did": [
          "timer 3: set for 10000 ms",
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
      },
      {
        "step": "the restored log no longer exists",
        "did": [
          "stream 4: closed",
          "live log: marked ended"
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
        "did": [],
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
  },
  {
    "scenario": "a connecting stream is parked and restored",
    "steps": [
      {
        "step": "the page starts but the socket has not opened",
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
        "step": "pagehide, kept for Back",
        "did": [
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
        "step": "the fresh stream survives four errors",
        "did": [],
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
    "scenario": "initial streams become ready while the page is parked",
    "steps": [
      {
        "step": "pagehide before startup completes",
        "did": [],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 0
        }
      },
      {
        "step": "initial streams requested while parked",
        "did": [],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 2
        }
      },
      {
        "step": "pageshow, restored",
        "did": [
          "stream 1: opened /api/events?scope=root-depth-2",
          "stream 2: opened /api/stream?path=run.jsonl&cursor=120"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2",
            "/api/stream?path=run.jsonl&cursor=120"
          ],
          "timers": [],
          "parked": 0
        }
      }
    ]
  },
  {
    "scenario": "a page's file watches follow its event stream's connection",
    "steps": [
      {
        "step": "the page starts, and stream 1 sends the snapshot of connection c1",
        "did": [
          "stream 1: opened /api/events?scope=root-depth-2",
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
        "step": "a table read at g1 watches its file: registered on c1",
        "did": [
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"people.csv\",\"generation\":\"g1\"}",
          "table: watch live"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0,
          "watches": [
            {
              "path": "people.csv",
              "state": "live",
              "reason": null,
              "generation": "g1",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "the file changes: file.changed on stream 1 tells the table once",
        "did": [
          "table: people.csv is now g2"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0,
          "watches": [
            {
              "path": "people.csv",
              "state": "live",
              "reason": null,
              "generation": "g2",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "a resync: stream 1 ends and the page waits to reconnect",
        "did": [
          "request: GET /api/catalog",
          "timer 1: cancelled",
          "stream 1: closed",
          "timer 2: set for 2000 ms"
        ],
        "after": {
          "streams": [],
          "timers": [
            "2000 ms"
          ],
          "parked": 0,
          "watches": [
            {
              "path": "people.csv",
              "state": "live",
              "reason": null,
              "generation": "g2",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "the file changes while no stream is open",
        "did": [],
        "after": {
          "streams": [],
          "timers": [
            "2000 ms"
          ],
          "parked": 0,
          "watches": [
            {
              "path": "people.csv",
              "state": "live",
              "reason": null,
              "generation": "g2",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "stream 2 sends the same tree for c2: the watch registers again with g2, and hears g3",
        "did": [
          "timer 2: fired",
          "stream 2: opened /api/events?scope=root-depth-2",
          "timer 3: set for 10000 ms",
          "request: GET /api/catalog",
          "tree: snapshot of 1 entries applied",
          "request: POST /api/events/watch {\"connection\":\"c2\",\"path\":\"people.csv\",\"generation\":\"g2\"}",
          "table: people.csv is now g3"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0,
          "watches": [
            {
              "path": "people.csv",
              "state": "live",
              "reason": null,
              "generation": "g3",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "the server restarts: it holds no connection",
        "did": [
          "timer 3: cancelled"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [],
          "parked": 0,
          "watches": [
            {
              "path": "people.csv",
              "state": "live",
              "reason": null,
              "generation": "g3",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "a tree's container watches a deep file: c2 is refused, so it waits",
        "did": [
          "request: POST /api/events/watch {\"connection\":\"c2\",\"path\":\"deep/notes.txt\",\"generation\":\"n1\"}",
          "tree: watch waiting (unknown_connection)"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [],
          "parked": 0,
          "watches": [
            {
              "path": "people.csv",
              "state": "live",
              "reason": null,
              "generation": "g3",
              "listeners": 1
            },
            {
              "path": "deep/notes.txt",
              "state": "waiting",
              "reason": "unknown_connection",
              "generation": "n1",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "the reconnected stream 3 sends c3: both watches register on it",
        "did": [
          "stream 2: closed",
          "timer 4: set for 4000 ms",
          "timer 4: fired",
          "stream 3: opened /api/events?scope=root-depth-2",
          "timer 5: set for 10000 ms",
          "request: GET /api/catalog",
          "event: metabrowser:inventory-change snapshot anything may have changed",
          "request: POST /api/events/watch {\"connection\":\"c3\",\"path\":\"people.csv\",\"generation\":\"g3\"}",
          "request: POST /api/events/watch {\"connection\":\"c3\",\"path\":\"deep/notes.txt\",\"generation\":\"n1\"}",
          "tree: watch live"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0,
          "watches": [
            {
              "path": "people.csv",
              "state": "live",
              "reason": null,
              "generation": "g3",
              "listeners": 1
            },
            {
              "path": "deep/notes.txt",
              "state": "live",
              "reason": null,
              "generation": "n1",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "pagehide, kept for Back",
        "did": [
          "timer 5: cancelled",
          "stream 3: closed"
        ],
        "after": {
          "streams": [],
          "timers": [],
          "parked": 1,
          "watches": [
            {
              "path": "people.csv",
              "state": "live",
              "reason": null,
              "generation": "g3",
              "listeners": 1
            },
            {
              "path": "deep/notes.txt",
              "state": "live",
              "reason": null,
              "generation": "n1",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "pageshow, restored: stream 4 sends c4, and the watches move to it",
        "did": [
          "stream 4: opened /api/events?scope=root-depth-2",
          "timer 6: set for 10000 ms",
          "request: GET /api/catalog",
          "event: metabrowser:inventory-change snapshot anything may have changed",
          "request: POST /api/events/watch {\"connection\":\"c4\",\"path\":\"people.csv\",\"generation\":\"g3\"}",
          "request: POST /api/events/watch {\"connection\":\"c4\",\"path\":\"deep/notes.txt\",\"generation\":\"n1\"}"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0,
          "watches": [
            {
              "path": "people.csv",
              "state": "live",
              "reason": null,
              "generation": "g3",
              "listeners": 1
            },
            {
              "path": "deep/notes.txt",
              "state": "live",
              "reason": null,
              "generation": "n1",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "the table is disposed: its file is unregistered",
        "did": [
          "request: POST /api/events/watch {\"connection\":\"c4\",\"path\":\"people.csv\",\"watch\":false}"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0,
          "watches": [
            {
              "path": "deep/notes.txt",
              "state": "live",
              "reason": null,
              "generation": "n1",
              "listeners": 1
            }
          ]
        }
      }
    ]
  }
]
? 0
```

An expanded folder that failed while disconnected retries after an authoritative
snapshot or filtered tree response.
Successful, collapsed, loading, pinned, Recent, and disposed views keep their state;
failed retries wait for another recovery.

```console
$ node tests/dom/page-reconnect-behavior.js
{
  "observations": [
    {
      "filtered": false,
      "calls": [
        [
          "retire",
          "gone.md"
        ],
        [
          "patch",
          "excluded"
        ]
      ]
    },
    {
      "filtered": true,
      "calls": [
        [
          "retire",
          "gone.md"
        ],
        [
          "filtered-tree",
          true
        ]
      ]
    }
  ],
  "resumed": 1,
  "recovery": [
    {
      "filtered": false,
      "folder": "docs",
      "restored": "docs/guide.md",
      "parses": 1,
      "snapshots": 1,
      "healthyCacheRetained": true,
      "staleReadRejected": true
    },
    {
      "filtered": true,
      "folder": "docs",
      "restored": "docs/guide.md",
      "parses": 1,
      "snapshots": 1,
      "healthyCacheRetained": true,
      "staleReadRejected": true
    }
  ],
  "boundaries": {
    "kept": [
      "successful",
      "collapsed",
      "pinned",
      "Recent",
      "detached",
      "disposed"
    ],
    "inFlight": "joined; invalidated answer revalidated",
    "failedRetry": "waits for authoritative recovery",
    "collapsedAncestor": "expanded child repaired; own-collapsed body retained",
    "suppliedChildren": "stale failure removed without fetching"
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
