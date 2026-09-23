---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Source Freshness

A page on a served mirror polls `/api/source/status` while it is visible, asks for one
background refresh when the mirror is stale, shows when it was last fetched, offers the
newer commit when a refresh moved the pinned ref, and switches the pin with
`POST /api/source/pin`. The Git panel turns a history cursor a refresh invalidated into
a typed stale state with a reload action.

This browserless session loads the production `static/source-freshness.js` and
`static/git-history-window.js` and plays the server’s side from
`tests/fixtures/source-freshness-responses.json`: what the in-process application
answered while a real mirror went stale, refreshed, gained a newer commit, switched its
pin, lost its origin, and invalidated an open all-branch history cursor.
`tests/test_source_freshness_session.py` replays that story and fails when the recording
drifts. Timers, the clock, visibility, and paint are injected; each step records the
requests the page made, the poll it scheduled (`fast` while a refresh runs, `slow`
otherwise), whether it reloaded, and what it would paint.

```console
$ node tests/dom/source-freshness-session.js
{
  "steps": [
    {
      "step": "open a stale page",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {}"
      ],
      "timer": "fast",
      "reloads": 0,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 6 d ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "poll while the refresh runs",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "fast",
      "reloads": 0,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 6 d ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "an unchanged status is a 304",
      "requests": [
        "GET /api/source/status If-None-Match: \"s2\""
      ],
      "timer": "fast",
      "reloads": 0,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 6 d ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the refresh brought a newer commit",
      "requests": [
        "GET /api/source/status If-None-Match: \"s2\""
      ],
      "timer": "slow",
      "reloads": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "Newer commit on topic [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    },
    {
      "step": "a hidden page stops polling",
      "requests": [],
      "timer": null,
      "reloads": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "Newer commit on topic [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    },
    {
      "step": "a page shown again polls at once",
      "requests": [
        "GET /api/source/status If-None-Match: \"s3\""
      ],
      "timer": "slow",
      "reloads": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "Newer commit on topic [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    },
    {
      "step": "accept the offer",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/topic\"}"
      ],
      "timer": "slow",
      "reloads": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "Newer commit on topic [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    },
    {
      "step": "another tab switched the pin",
      "requests": [
        "GET /api/source/status If-None-Match: \"s1\""
      ],
      "timer": "slow",
      "reloads": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload]",
        "error": null
      }
    },
    {
      "step": "reload after a switch elsewhere",
      "requests": [],
      "timer": "slow",
      "reloads": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload]",
        "error": null
      }
    },
    {
      "step": "a refresh failed; the pin is still served",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "slow",
      "reloads": 0,
      "paint": {
        "label": "Refresh failed · fetched 5 min ago",
        "tone": "warning",
        "detail": "The origin could not be read. The pinned revision is still served from the mirror.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a refused switch says why and does not reload",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/topic\"}"
      ],
      "timer": "slow",
      "reloads": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "Newer commit on topic [Switch] → refs/remotes/origin/topic",
        "error": "Could not switch (selection_not_found)"
      }
    },
    {
      "step": "open a stale page whose origin is gone",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {}"
      ],
      "timer": "fast",
      "reloads": 0,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 6 d ago.",
        "offer": "Newer commit on topic [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    },
    {
      "step": "a stale page whose refresh fails asks once",
      "requests": [
        "GET /api/source/status",
        "GET /api/source/status If-None-Match: \"s2\""
      ],
      "timer": "slow",
      "reloads": 0,
      "paint": {
        "label": "Refresh failed · fetched 6 d ago",
        "tone": "warning",
        "detail": "The origin could not be read. The pinned revision is still served from the mirror.",
        "offer": "Newer commit on topic [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    },
    {
      "step": "shown again, a stale page asks again",
      "requests": [
        "GET /api/source/status If-None-Match: \"s2\"",
        "POST /api/source/refresh {}"
      ],
      "timer": "fast",
      "reloads": 0,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 6 d ago.",
        "offer": "Newer commit on topic [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    }
  ],
  "history": [
    {
      "failure": "a refresh moved the refs",
      "status": 409,
      "code": "history_stale",
      "initial": false,
      "means": "stale"
    },
    {
      "failure": "the session expired",
      "status": 410,
      "code": null,
      "initial": false,
      "means": "recover"
    },
    {
      "failure": "the cursor was rejected",
      "status": 400,
      "code": null,
      "initial": false,
      "means": "recover"
    },
    {
      "failure": "a conflict without a code",
      "status": 409,
      "code": null,
      "initial": false,
      "means": "recover"
    },
    {
      "failure": "the server failed",
      "status": 500,
      "code": null,
      "initial": false,
      "means": "failed"
    },
    {
      "failure": "the first page was stale",
      "status": 409,
      "code": "history_stale",
      "initial": true,
      "means": "failed"
    }
  ]
}
? 0
```
