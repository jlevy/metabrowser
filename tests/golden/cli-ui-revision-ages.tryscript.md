---
cwd: ../..
sandbox: false
---
# Golden Test: A Revision’s Page While Its File Ages Are Read

A Git revision’s files get their ages from `git last-modified`, which the server runs in
the background and never makes a page wait for.
A tree, a grouped tree, or a Recent list asked for before the answer lands says
`ages.state: "dating"` and has every file undated.
`static/revision-ages.js` watches for that state and asks `/api/index/progress`, which
carries the same state, until it changes; then it asks the shell to draw once more, so
the rows that had no age get one without the reader doing anything.

This browserless session runs the real module under fake timers and a scripted progress
route, once through the controller and once through `mount`, the glue the page runs.
The transcript pins these behaviors:

- A response with no `ages`, or one that says the answer is in (`ready`, `partial`,
  `unavailable`), starts no watch and holds no timer.
- A response that says `dating` starts one watch; seeing `dating` again while it runs
  adds no second timer.
  The watch asks at the pace the page’s settings name.
- While the answer is `dating` the watch keeps asking.
  When it lands, `ready` or `partial`, the shell is asked to draw once with the state,
  and the watch holds nothing.
- A poll that fails ends the watch without drawing; the next tree request that says
  `dating` starts it again.
- A watch gives up once it has run well past the server’s own bound on a read, and a
  response that says the answer landed ends it at once.

```console
$ node tests/dom/revision-ages-session.js
{
  "a response with no ages is not about file ages": {
    "watching": false,
    "timers": 0,
    "progressRequests": 0,
    "landed": []
  },
  "an answer that has landed starts no watch": {
    "watching": false,
    "timers": 0,
    "progressRequests": 0,
    "landed": []
  },
  "dating starts one watch that polls until the answer lands, then draws once": {
    "observed": {
      "watching": true,
      "timers": 1,
      "progressRequests": 0,
      "landed": [],
      "delays": [
        500
      ]
    },
    "observedAgain": {
      "watching": true,
      "timers": 1,
      "progressRequests": 0,
      "landed": [],
      "delays": [
        500
      ]
    },
    "firstPoll": {
      "watching": true,
      "timers": 1,
      "progressRequests": 1,
      "landed": []
    },
    "secondPoll": {
      "watching": true,
      "timers": 1,
      "progressRequests": 2,
      "landed": []
    },
    "landed": {
      "watching": false,
      "timers": 0,
      "progressRequests": 3,
      "landed": [
        "landed {\"state\":\"ready\",\"dated\":7}"
      ]
    }
  },
  "a partial answer is an answer: it draws once and stops": {
    "watching": false,
    "timers": 0,
    "progressRequests": 1,
    "landed": [
      "landed {\"state\":\"partial\",\"dated\":3,\"older_than\":1700000000}"
    ]
  },
  "a poll that fails ends the watch without drawing": {
    "watching": false,
    "timers": 0,
    "progressRequests": 1,
    "landed": []
  },
  "a response that says the answer landed ends the watch": {
    "watching": false,
    "timers": 0,
    "progressRequests": 0,
    "landed": []
  },
  "a watch that outlasts the server's own bound gives up": {
    "watching": false,
    "timers": 0,
    "progressRequests": 1,
    "landed": []
  },
  "the page's glue asks the progress route at the settings' pace": {
    "delays": [
      250,
      250
    ],
    "asked": [
      {
        "url": "/api/index/progress",
        "options": {
          "cache": "no-store"
        }
      },
      {
        "url": "/api/index/progress",
        "options": {
          "cache": "no-store"
        }
      }
    ],
    "landed": [
      {
        "state": "partial",
        "dated": 2
      }
    ],
    "watching": false
  }
}
? 0
```
