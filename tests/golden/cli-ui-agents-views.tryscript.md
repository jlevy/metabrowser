---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: the agents views’ state machines

The agents home, the session list, and the Session view read data that the `agents`
routes own; their goldens are `cli-api-agents-*.tryscript.md`. This session runs the
production modules for what the browser owns, with the clock, the timers, and the page’s
visibility moved by hand:

- **The session list’s state.** The list opens without automatic reviews, newest
  activity first. Each filter change returns the first page, a column sorts as the route
  defaults it and reverses on a second choice, a page never leaves the rows a response
  says exist, and the state names the `sessions` request.
  The opening request is the one `cli-api-agents-views.tryscript.md` sends the route.
- **The poll.** One request is in flight at most, none is made while the page is hidden,
  a shown page asks at once, a failure doubles the wait up to a cap, a good answer
  resets it, a tick that answers `false` ends the poll (how the home stops when its
  summary is complete), and disposing it aborts the request and leaves no timer.
- **What the home derives.** The activity window, the size histogram, the progress
  sentence, and the ages and durations.
- **The markup.** A session table, whose sorted column says so and whose titles are
  escaped, a two-line session row, as the home’s Active sessions and Latest sessions
  draw it (the agent, the title link, and the age on the first line, the project and the
  model on the second, parted by the design’s separator), and an event row in its kind’s
  and its tool family’s color class.

```console
$ node tests/dom/agents-views-session.js
{
  "session list state": {
    "the list opens without automatic reviews, newest activity first": {
      "offset": 0,
      "sort": "activity desc",
      "query": "folder=&sort=activity&order=desc&limit=50&origin=human%2Cscheduled%2Csubagent%2Cautomation"
    },
    "showing reviews too asks for every origin": {
      "offset": 0,
      "sort": "activity desc",
      "query": "folder=&sort=activity&order=desc&limit=50"
    },
    "hiding them again": {
      "offset": 0,
      "sort": "activity desc",
      "query": "folder=&sort=activity&order=desc&limit=50&origin=human%2Cscheduled%2Csubagent%2Cautomation"
    },
    "a second page": {
      "offset": 50,
      "sort": "activity desc",
      "query": "folder=&sort=activity&order=desc&limit=50&offset=50&origin=human%2Cscheduled%2Csubagent%2Cautomation"
    },
    "a third": {
      "offset": 100,
      "sort": "activity desc",
      "query": "folder=&sort=activity&order=desc&limit=50&offset=100&origin=human%2Cscheduled%2Csubagent%2Cautomation"
    },
    "a fourth stops at the last page": {
      "offset": 100,
      "sort": "activity desc",
      "query": "folder=&sort=activity&order=desc&limit=50&offset=100&origin=human%2Cscheduled%2Csubagent%2Cautomation"
    },
    "the pager after the third page": {
      "first": 101,
      "last": 130,
      "total": 130,
      "hasPrevious": true,
      "hasNext": false
    },
    "back one page": {
      "offset": 50,
      "sort": "activity desc",
      "query": "folder=&sort=activity&order=desc&limit=50&offset=50&origin=human%2Cscheduled%2Csubagent%2Cautomation"
    },
    "a filter returns to the first page": {
      "offset": 0,
      "sort": "activity desc",
      "query": "folder=&sort=activity&order=desc&limit=50&agent=codex&origin=human%2Cscheduled%2Csubagent%2Cautomation"
    },
    "a text column sorts as the route defaults it: ascending": {
      "offset": 0,
      "sort": "title asc",
      "query": "folder=&sort=title&order=asc&limit=50&agent=codex&origin=human%2Cscheduled%2Csubagent%2Cautomation"
    },
    "the same column reverses": {
      "offset": 0,
      "sort": "title desc",
      "query": "folder=&sort=title&order=desc&limit=50&agent=codex&origin=human%2Cscheduled%2Csubagent%2Cautomation"
    },
    "a numeric column sorts largest first": {
      "offset": 0,
      "sort": "size desc",
      "query": "folder=&sort=size&order=desc&limit=50&agent=codex&origin=human%2Cscheduled%2Csubagent%2Cautomation"
    },
    "the filters together": {
      "query": "folder=&sort=size&order=desc&limit=50&agent=codex&origin=human%2Cscheduled%2Csubagent%2Cautomation&status=running%2Cfailed&project=%2Fwork%2Falpha&since=1799395200"
    },
    "a status chip toggled off": {
      "offset": 0,
      "sort": "size desc",
      "query": "folder=&sort=size&order=desc&limit=50&agent=codex&origin=human%2Cscheduled%2Csubagent%2Cautomation&status=failed&project=%2Fwork%2Falpha&since=1799395200"
    },
    "and back on, in the route's order": {
      "offset": 0,
      "sort": "size desc",
      "query": "folder=&sort=size&order=desc&limit=50&agent=codex&origin=human%2Cscheduled%2Csubagent%2Cautomation&status=running%2Cfailed&project=%2Fwork%2Falpha&since=1799395200"
    }
  },
  "poll": {
    "a started poll waits one interval": {
      "ticks": [],
      "timers": 1
    },
    "then asks": {
      "ticks": [
        "tick at 1000"
      ],
      "state": {
        "running": true,
        "inFlight": false,
        "failures": 0,
        "waitMs": 1000
      }
    },
    "a hidden page asks nothing": {
      "ticks": [
        "tick at 1000"
      ]
    },
    "shown again, it asks at once": {
      "ticks": [
        "tick at 1000",
        "tick at 4000"
      ]
    },
    "a failure doubles the wait": {
      "ticks": [
        "tick at 1000",
        "tick at 4000",
        "tick at 5000",
        "error"
      ],
      "state": {
        "running": true,
        "inFlight": false,
        "failures": 1,
        "waitMs": 2000
      }
    },
    "a good answer resets it": {
      "state": {
        "running": true,
        "inFlight": false,
        "failures": 0,
        "waitMs": 1000
      }
    },
    "a slow request is not queued behind itself": {
      "inFlight": true,
      "requestsWhileHeld": 1
    },
    "disposing aborts the request in flight": {
      "inFlight": false,
      "running": false,
      "timers": 0,
      "requestsAfter": 0
    },
    "a tick that answers false ends the poll, as a complete summary does": {
      "calls": 3,
      "running": false,
      "timers": 0
    },
    "a retried ask backs off on a failure, resets on an answer, and ends on a refusal": {
      "asked": [
        "down",
        "again",
        "refused"
      ],
      "running": false,
      "failures": 0
    },
    "which failures are worth asking again": [
      true,
      true,
      true,
      false,
      false
    ],
    "a summary poll backs off on a failed load and ends when the summary is complete": {
      "afterFirst": 0,
      "afterFailure": {
        "failures": 1,
        "waitMs": 2000
      },
      "unasked": 0,
      "running": false
    }
  },
  "home": {
    "activity window": {
      "bars": 90,
      "first": "2026-10-18",
      "last": "2027-01-15",
      "peak": 4,
      "total": 6,
      "heights": [
        0,
        1,
        0.5
      ]
    },
    "size histogram": {
      "bars": [
        {
          "label": "1 KB to 4 KB",
          "count": 3,
          "height": 0.5
        },
        {
          "label": "4 KB to 16 KB",
          "count": 6,
          "height": 1
        }
      ],
      "peak": 6
    },
    "progress while summarizing": {
      "phase": "summarizing",
      "text": "Indexing session details… 5 of 10 checked."
    },
    "progress at first, with nothing found yet": {
      "phase": "scanning",
      "text": "Looking for sessions…"
    },
    "progress when complete": {
      "phase": "complete",
      "text": "Session details indexed."
    },
    "progress when complete with an unreadable session": {
      "phase": "complete",
      "text": "Session indexing finished. 1 could not be read."
    },
    "the session page while the catalog's first pass runs": [
      "Reading the session catalog…",
      "Looking for sessions…",
      "Indexing session details… 0 of 12 checked."
    ],
    "what the events say": {
      "none match, the scan reached the end": {
        "notice": "No events match.",
        "note": ""
      },
      "none matched yet, more to scan": {
        "notice": "No events matched yet.",
        "note": ""
      },
      "none matched, the bound stopped the scan": {
        "notice": "No events matched in the part of the session that could be searched.",
        "note": ""
      },
      "some, the scan went on": {
        "notice": "",
        "note": ""
      },
      "some, the bound stopped the scan": {
        "notice": "",
        "note": "Showing the first events the scan reached; the rest of this session is not searched."
      }
    },
    "ages": [
      "just now",
      "40 s ago",
      "10 min ago",
      "2 h ago",
      "4 d ago"
    ],
    "durations": [
      "31 s",
      "4 min 12 s",
      "2 h 5 min"
    ]
  },
  "markup": {
    "no value a session holds reaches the row as markup": true,
    "a session row's first line holds the agent, the title link, and the age last": true,
    "its second line is the status, the project, and the model, parted by the design's separator": true,
    "a row with neither leaves the line empty and no stray separator": true,
    "a title with no file is plain text in the row": true,
    "the list names itself": true,
    "the sorted column says so": true,
    "an unsorted column offers its sort": true,
    "a title is escaped": true,
    "a session with a file is a link to it": true,
    "a session with no file is plain text": true,
    "a running status wears the running badge": true,
    "no rows is a sentence": "<p class=\"agents-empty\">No sessions match these filters.</p>",
    "an event wears its kind's and its tool family's color class": true,
    "an unknown kind is neutral": true,
    "a replayed event is marked apart": true
  }
}
? 0
```
