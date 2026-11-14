---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: One Root-Summary Request at a Time

Every root aggregate upsert, every tree load, and the recency menu ask the page for a
fresh `/api/tree?depth=0`, and each answer costs the server a pass over the whole index.
A live tree upserts its root on every write, so a page that sent one request per ask
held a pile of identical multi-second requests, and in WebKit, which sends them in
parallel, they took every connection the Commits tab needed
(`explorations/tree-summary-storm/README.md`).

This browserless session runs the shell’s summary refresh, the block of `static/app.js`
from its introducing comment to the tree cache, verbatim against
`createRootSummaryRefresh` in `static/navigation.js`. Only the browser is a double: the
clock and its timers, `fetch` and a server that answers each request after a set time,
and the document’s summary row, Files panel, and visibility.

Each step lists what the page `did`, in order: each request it sent, how many were then
in flight, when the server answered, and what it painted.
Its `after` counts the asks, the requests, and the most requests in flight at once.
The transcript pins these behaviors:

- A live tree that upserts its root every 100 ms, with each answer taking 3.2 s, gets
  one request in flight at a time, and the next waits twice what the last one cost.
- An answer that takes 20 s is followed by 40 s of spacing: the 30 s cap bounds only the
  backoff after failures, never the spacing a slow answer earned.
- Asks made while a request was in flight are answered by one more request after the
  writes stop.
- An isolated change on a quiet tree is requested after the debounce alone.
- A failed request is asked again after a backoff that doubles with each failure.
- A hidden page, or a Files panel behind another tab, requests nothing, and is refreshed
  once when it is shown again.

```console
$ node tests/dom/root-summary-refresh-session.js
[
  {
    "scenario": "a live tree upserts its root every 100 ms and each answer takes 3.2 s",
    "steps": [
      {
        "step": "the root is upserted every 100 ms for 30 s",
        "did": [
          "t=500 sent #1 /api/tree?depth=0 (1 in flight)",
          "t=3700 #1 answered",
          "t=3700 painted 1 files",
          "t=10100 sent #2 /api/tree?depth=0 (1 in flight)",
          "t=13300 #2 answered",
          "t=13300 painted 2 files",
          "t=19700 sent #3 /api/tree?depth=0 (1 in flight)",
          "t=22900 #3 answered",
          "t=22900 painted 3 files",
          "t=29300 sent #4 /api/tree?depth=0 (1 in flight)"
        ],
        "after": {
          "asks": 300,
          "requests": 4,
          "maxInFlight": 1,
          "inFlight": 1
        }
      },
      {
        "step": "the writes stop",
        "did": [
          "t=32500 #4 answered",
          "t=32500 painted 4 files",
          "t=38900 sent #5 /api/tree?depth=0 (1 in flight)",
          "t=42100 #5 answered",
          "t=42100 painted 5 files"
        ],
        "after": {
          "asks": 300,
          "requests": 5,
          "maxInFlight": 1,
          "inFlight": 0
        }
      }
    ]
  },
  {
    "scenario": "a live tree whose every answer takes 20 s",
    "steps": [
      {
        "step": "the root is upserted every 100 ms for 70 s",
        "did": [
          "t=500 sent #1 /api/tree?depth=0 (1 in flight)",
          "t=20500 #1 answered",
          "t=20500 painted 1 files",
          "t=60500 sent #2 /api/tree?depth=0 (1 in flight)"
        ],
        "after": {
          "asks": 700,
          "requests": 2,
          "maxInFlight": 1,
          "inFlight": 1
        }
      }
    ]
  },
  {
    "scenario": "an isolated change on a quiet tree",
    "steps": [
      {
        "step": "one write",
        "did": [
          "t=500 sent #1 /api/tree?depth=0 (1 in flight)",
          "t=800 #1 answered",
          "t=800 painted 1 files"
        ],
        "after": {
          "asks": 1,
          "requests": 1,
          "maxInFlight": 1,
          "inFlight": 0
        }
      },
      {
        "step": "another write, long after",
        "did": [
          "t=20500 sent #2 /api/tree?depth=0 (1 in flight)",
          "t=20800 #2 answered",
          "t=20800 painted 2 files"
        ],
        "after": {
          "asks": 2,
          "requests": 2,
          "maxInFlight": 1,
          "inFlight": 0
        }
      }
    ]
  },
  {
    "scenario": "the server fails the first two requests",
    "steps": [
      {
        "step": "one write, and no other ask",
        "did": [
          "t=500 sent #1 /api/tree?depth=0 (1 in flight)",
          "t=800 #1 failed: 503",
          "t=4800 sent #2 /api/tree?depth=0 (1 in flight)",
          "t=5100 #2 failed: 503",
          "t=13100 sent #3 /api/tree?depth=0 (1 in flight)",
          "t=13400 #3 answered",
          "t=13400 painted 3 files"
        ],
        "after": {
          "asks": 1,
          "requests": 3,
          "maxInFlight": 1,
          "inFlight": 0
        }
      }
    ]
  },
  {
    "scenario": "a page that is hidden while its tree changes",
    "steps": [
      {
        "step": "hidden, the root is upserted every 100 ms for 10 s",
        "did": [],
        "after": {
          "asks": 100,
          "requests": 0,
          "maxInFlight": 0,
          "inFlight": 0
        }
      },
      {
        "step": "the page is shown",
        "did": [
          "t=10500 sent #1 /api/tree?depth=0 (1 in flight)",
          "t=10800 #1 answered",
          "t=10800 painted 1 files"
        ],
        "after": {
          "asks": 100,
          "requests": 1,
          "maxInFlight": 1,
          "inFlight": 0
        }
      }
    ]
  },
  {
    "scenario": "a Files panel behind the Commits tab while its tree changes",
    "steps": [
      {
        "step": "Commits in front, the root is upserted every 100 ms for 10 s",
        "did": [],
        "after": {
          "asks": 100,
          "requests": 0,
          "maxInFlight": 0,
          "inFlight": 0
        }
      },
      {
        "step": "Files comes to the front",
        "did": [
          "t=10500 sent #1 /api/tree?depth=0 (1 in flight)",
          "t=10800 #1 answered",
          "t=10800 painted 1 files"
        ],
        "after": {
          "asks": 100,
          "requests": 1,
          "maxInFlight": 1,
          "inFlight": 0
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
