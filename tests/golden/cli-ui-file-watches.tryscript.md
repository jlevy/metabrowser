---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Page’s File Watches Once Registered

A view that shows a live file, a table or a container’s children in the tree, watches it
on the page’s one event stream (`static/file-watches.js`,
`docs/project/architecture/arch-live-delivery.md`).
`cli-ui-page-connections.tryscript.md` pins how a watch follows that stream’s
connection; this session pins what the page does with its watches once registered.

It runs `static/file-watches.js` on the page `tests/dom/page-connections-session.js`
builds, with `app.js`’s `watchContainer` and `loadContainerChildren` extracted verbatim.
The server holds each connection’s watched paths up to a bound, records them after each
request (`server: c1 watches [...]`), and can hold its answers as a slow server does.
Each step lists what the page `did`, in order, and what it holds `after`.

- A watch released before its registration is answered is unregistered after that
  answer, so leaving views quickly never fills the connection’s bound.
- A watch refused for want of room (`too_many_watches`) registers again once another
  watch is released, after the server has let that one go.
- While the page is hidden its watches are unregistered, so the server polls nothing for
  it; shown again, each registers with the generation it holds, and a change made while
  it was hidden reaches its reader once.
- A tree container whose children were read follows its file: changes in a burst make
  one read of its children after the window, one read runs at a time and a change during
  it makes one more, children that read the same are not drawn again, a collapsed
  container’s children are read on its next expand, and a row the tree drops releases
  its watch though its file never changes.

```console
$ node tests/dom/file-watches-session.js
[
  {
    "scenario": "a page's file watches are released, retried, and paused while hidden",
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
        "step": "a table watches a.csv and leaves before the slow answer: unregistered after it",
        "did": [
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"a.csv\",\"generation\":\"a1\"}",
          "server: c1 watches [a.csv]",
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"a.csv\",\"watch\":false}",
          "server: c1 watches []"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0,
          "watches": []
        }
      },
      {
        "step": "tables watch b.csv, c.csv, and d.csv: past the bound of 2, d is refused",
        "did": [
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"b.csv\",\"generation\":\"b1\"}",
          "server: c1 watches [b.csv]",
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"c.csv\",\"generation\":\"c1\"}",
          "server: c1 watches [b.csv, c.csv]",
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"d.csv\",\"generation\":\"d1\"}",
          "b: watch live",
          "c: watch live",
          "d: watch refused (too_many_watches)"
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
              "path": "b.csv",
              "state": "live",
              "reason": null,
              "generation": "b1",
              "listeners": 1
            },
            {
              "path": "c.csv",
              "state": "live",
              "reason": null,
              "generation": "c1",
              "listeners": 1
            },
            {
              "path": "d.csv",
              "state": "refused",
              "reason": "too_many_watches",
              "generation": "d1",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "b's table leaves: once b is unregistered, d registers again and is live",
        "did": [
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"b.csv\",\"watch\":false}",
          "server: c1 watches [c.csv]",
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"d.csv\",\"generation\":\"d1\"}",
          "server: c1 watches [c.csv, d.csv]",
          "d: watch live"
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
              "path": "c.csv",
              "state": "live",
              "reason": null,
              "generation": "c1",
              "listeners": 1
            },
            {
              "path": "d.csv",
              "state": "live",
              "reason": null,
              "generation": "d1",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "the page is hidden: every watch is unregistered, so none is polled",
        "did": [
          "c: watch waiting (hidden)",
          "d: watch waiting (hidden)",
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"c.csv\",\"watch\":false}",
          "server: c1 watches [d.csv]",
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"d.csv\",\"watch\":false}",
          "server: c1 watches []"
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
              "path": "c.csv",
              "state": "waiting",
              "reason": "hidden",
              "generation": "c1",
              "listeners": 1
            },
            {
              "path": "d.csv",
              "state": "waiting",
              "reason": "hidden",
              "generation": "d1",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "d.csv changes while the page is hidden: nothing is told",
        "did": [],
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
              "path": "c.csv",
              "state": "waiting",
              "reason": "hidden",
              "generation": "c1",
              "listeners": 1
            },
            {
              "path": "d.csv",
              "state": "waiting",
              "reason": "hidden",
              "generation": "d1",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "the page is shown: each registers again with what it holds, and d hears d2 once",
        "did": [
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"c.csv\",\"generation\":\"c1\"}",
          "server: c1 watches [c.csv]",
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"d.csv\",\"generation\":\"d1\"}",
          "server: c1 watches [c.csv, d.csv]",
          "c: watch live",
          "d: watch live",
          "d: d.csv is now d2"
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
              "path": "c.csv",
              "state": "live",
              "reason": null,
              "generation": "c1",
              "listeners": 1
            },
            {
              "path": "d.csv",
              "state": "live",
              "reason": null,
              "generation": "d2",
              "listeners": 1
            }
          ]
        }
      }
    ]
  },
  {
    "scenario": "a tree container's children follow its file",
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
        "step": "app.db expanded: its children read and drawn, and its file followed",
        "did": [
          "tree: app.db's children drawn: loading",
          "request: GET /api/plugin/sqlite/children?path=app.db",
          "asset: file-watches",
          "tree: app.db's children drawn: users | orders",
          "tree: filters applied",
          "tree: keyboard synchronized",
          "tree: observed #tree-content and its subtree",
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"app.db\"}",
          "server: c1 watches [app.db]"
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
              "path": "app.db",
              "state": "live",
              "reason": null,
              "generation": "g1",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "its file changes three times in a burst: one read is due",
        "did": [
          "timer 2: set for 300 ms"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms",
            "300 ms"
          ],
          "parked": 0,
          "watches": [
            {
              "path": "app.db",
              "state": "live",
              "reason": null,
              "generation": "g4",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "the window ends: the children read once and drawn again",
        "did": [
          "timer 2: fired",
          "request: GET /api/plugin/sqlite/children?path=app.db",
          "asset: file-watches",
          "tree: app.db's children drawn: users | orders | items",
          "tree: filters applied",
          "tree: keyboard synchronized"
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
              "path": "app.db",
              "state": "live",
              "reason": null,
              "generation": "g4",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "a change that leaves the children as they were: read, not drawn",
        "did": [
          "timer 3: set for 300 ms",
          "timer 3: fired",
          "request: GET /api/plugin/sqlite/children?path=app.db",
          "asset: file-watches"
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
              "path": "app.db",
              "state": "live",
              "reason": null,
              "generation": "g5",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "a change while a slow read runs: it waits for that read",
        "did": [
          "timer 4: set for 300 ms",
          "timer 4: fired",
          "request: GET /api/plugin/sqlite/children?path=app.db"
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
              "path": "app.db",
              "state": "live",
              "reason": null,
              "generation": "g7",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "the slow read answers and is drawn: one more read is due",
        "did": [
          "asset: file-watches",
          "tree: app.db's children drawn: users | items",
          "tree: filters applied",
          "tree: keyboard synchronized",
          "timer 5: set for 300 ms"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms",
            "300 ms"
          ],
          "parked": 0,
          "watches": [
            {
              "path": "app.db",
              "state": "live",
              "reason": null,
              "generation": "g7",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "the next window ends: the children read again, unchanged since",
        "did": [
          "timer 5: fired",
          "request: GET /api/plugin/sqlite/children?path=app.db",
          "asset: file-watches"
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
              "path": "app.db",
              "state": "live",
              "reason": null,
              "generation": "g7",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "app.db collapsed, then changed: its children are read on the next expand",
        "did": [
          "timer 6: set for 300 ms",
          "timer 6: fired",
          "tree: children loaded: no"
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
              "path": "app.db",
              "state": "live",
              "reason": null,
              "generation": "g8",
              "listeners": 1
            }
          ]
        }
      },
      {
        "step": "the tree drops the row: its watch released, though the file is unchanged",
        "did": [
          "tree: no longer observed",
          "request: POST /api/events/watch {\"connection\":\"c1\",\"path\":\"app.db\",\"watch\":false}",
          "server: c1 watches []"
        ],
        "after": {
          "streams": [
            "/api/events?scope=root-depth-2"
          ],
          "timers": [
            "10000 ms"
          ],
          "parked": 0,
          "watches": []
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
