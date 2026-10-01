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

A page on a pin also names the commit it shows on its data requests, and a request
refused as `pin_changed` makes the row ask the status route at once.

A commit the mirror lacks, opened by its `/commit/<id>` address in a served page, is an
address not fetched too.
`/api/git/commit/<id>` answers `commit_not_found` and fetches nothing, and a link in
served content can send a reader to any such address, so the page asks for a fetch by
itself only when something is older than the server’s freshness window.
Inside the window the commit view says the commit is not in the mirror as fetched and
offers Retry, the reader’s own click, which always fetches.
The request is `POST /api/source/refresh` with `{"for": "commit"}`, which the server
holds to the same floor: it answers `fresh` when it starts no fetch of the mirror, so a
refresh of the data served beside the mirror is never taken for a fetch of its branches
and tags.
The view says the origin lacks the commit only after such a fetch ran, says the
fetch could not run when it did not, and reads a request that fails when the commit is
asked for again as a load failure, not as an answer about the commit.

This browserless session loads the production `static/source-freshness.js`,
`static/source-pin-guard.js`, and `static/git-history-window.js` and plays the server’s
side from `tests/fixtures/source-freshness-responses.json`: what the in-process
application answered while a real mirror went stale, refreshed, gained a newer commit,
switched its pin, lost its origin, invalidated an open all-branch history cursor, and
was asked for commits it did not have.
One part of that mirror is a stand-in: the data served beside it, as a pull request’s
record is, which fetches nothing and holds its refresh until released, so the answers
given while only it refreshes are recorded without a race.
`tests/test_source_freshness_session.py` replays that story and fails when the recording
drifts. Timers, the clock, visibility, and paint are injected; each step records the
requests the page made, the poll it scheduled (`fast` while a refresh runs, `slow`
otherwise), how many times it repainted (never for an unchanged status, so the row’s
announcement and focus stay put), whether it reloaded, and what it would paint.
A step with a commit view adds `commit`: what the preview pane shows for the commit and
how many times the step painted it.

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
      "repaints": 1,
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
      "repaints": 0,
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
      "repaints": 0,
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
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    },
    {
      "step": "a hidden page stops polling",
      "requests": [],
      "timer": null,
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
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
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
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
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
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
      "repaints": 1,
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
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload]",
        "error": null
      }
    },
    {
      "step": "switched before the first poll",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload]",
        "error": null
      }
    },
    {
      "step": "a URL selection waits for its fetch",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {}"
      ],
      "timer": "fast",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 6 d ago. The address this page was opened at is not in the mirror yet; it opens when the fetch brings it.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    },
    {
      "step": "the fetch brought the selection; the page goes to it",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload]",
        "error": null
      },
      "navigated": [
        "/view/g1-UkVBRE1FLm1k#L1"
      ]
    },
    {
      "step": "a page goes to a selection once",
      "requests": [
        "GET /api/source/status If-None-Match: \"s2\""
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload]",
        "error": null
      }
    },
    {
      "step": "the address is not on the origin",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Address not found · fetched 5 min ago",
        "tone": "warning",
        "detail": "The address this page was opened at is not on the origin, so the default branch is shown.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    },
    {
      "step": "the address could not be fetched",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Address not fetched · fetched 5 min ago",
        "tone": "warning",
        "detail": "The address this page was opened at could not be fetched, so the default branch is shown. The origin could not be read.",
        "offer": "Fetch the address again [Retry]",
        "error": null
      }
    },
    {
      "step": "retry the address",
      "requests": [
        "POST /api/source/refresh {}"
      ],
      "timer": "fast",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 5 min ago. The address this page was opened at is not in the mirror yet; it opens when the fetch brings it.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    },
    {
      "step": "inside the freshness window a missing commit starts no fetch",
      "requests": [],
      "timer": "slow",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "not_found",
        "title": "Commit not found · fetched 5 min ago",
        "detail": "This commit is not in the mirror as fetched 5 min ago.",
        "offer": "[Retry]"
      }
    },
    {
      "step": "retry fetches for the commit",
      "requests": [
        "POST /api/source/refresh {\"for\":\"commit\",\"retry\":true}"
      ],
      "timer": "fast",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "This commit is not in the mirror yet; it opens when the fetch brings it.",
        "offer": null
      }
    },
    {
      "step": "the commit waits while the fetch runs",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "fast",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 0,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "This commit is not in the mirror yet; it opens when the fetch brings it.",
        "offer": null
      }
    },
    {
      "step": "the fetch brought the commit; it opens",
      "requests": [
        "GET /api/source/status If-None-Match: \"s2\"",
        "GET /api/git/commit/92b31b0785485bd9eaa9619d198a779c2699295d"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "topic is now at 92b31b078548 [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 1,
        "shows": "92b31b0785485bd9eaa9619d198a779c2699295d"
      }
    },
    {
      "step": "the fetch ran and did not bring the commit",
      "requests": [
        "GET /api/source/status",
        "GET /api/git/commit/0123456789abcdef0123456789abcdef01234567"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "topic is now at 92b31b078548 [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "not_found",
        "title": "Commit not found · fetched 5 min ago",
        "detail": "This commit is not in the mirror, and the fetch from the origin did not bring it: no branch or tag there reaches it.",
        "offer": "[Retry]"
      }
    },
    {
      "step": "asking again failed; the view does not say not found",
      "requests": [
        "GET /api/source/status",
        "GET /api/git/commit/92b31b0785485bd9eaa9619d198a779c2699295d"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "topic is now at 92b31b078548 [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "failed",
        "title": "Could not load this commit.",
        "detail": "",
        "offer": null
      }
    },
    {
      "step": "only the data beside the mirror is refreshed",
      "requests": [
        "POST /api/source/refresh {\"for\":\"commit\"}"
      ],
      "timer": "fast",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "This commit is not in the mirror yet; it opens when the fetch brings it.",
        "offer": null
      }
    },
    {
      "step": "no fetch of the mirror ran, and the view does not say one did",
      "requests": [
        "GET /api/source/status",
        "GET /api/git/commit/0123456789abcdef0123456789abcdef01234567"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "not_found",
        "title": "Commit not found · fetched 5 min ago",
        "detail": "This commit is not in the mirror as fetched 5 min ago.",
        "offer": "[Retry]"
      }
    },
    {
      "step": "outside the window the page asks for the fetch itself",
      "requests": [
        "POST /api/source/refresh {\"for\":\"commit\"}"
      ],
      "timer": "fast",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 6 d ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "This commit is not in the mirror yet; it opens when the fetch brings it.",
        "offer": null
      }
    },
    {
      "step": "the commit could not be fetched",
      "requests": [
        "GET /api/source/status",
        "GET /api/git/commit/0123456789abcdef0123456789abcdef01234567"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refresh failed · fetched 6 d ago",
        "tone": "warning",
        "detail": "The origin could not be read. The pinned revision is still served from the mirror.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "fetch_failed",
        "title": "Commit not fetched · fetched 6 d ago",
        "detail": "This commit is not in the mirror, and it could not be fetched. The origin could not be read.",
        "offer": "[Retry]"
      }
    },
    {
      "step": "the reader left before the fetch ended",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refresh failed · fetched 6 d ago",
        "tone": "warning",
        "detail": "The origin could not be read. The pinned revision is still served from the mirror.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 0,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "This commit is not in the mirror yet; it opens when the fetch brings it.",
        "offer": null
      }
    },
    {
      "step": "a fetch of the mirror already running is joined",
      "requests": [
        "POST /api/source/refresh {\"for\":\"commit\"}"
      ],
      "timer": "fast",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "This commit is not in the mirror yet; it opens when the fetch brings it.",
        "offer": null
      }
    },
    {
      "step": "the server stopped answering while the fetch ran",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": "The server did not answer"
      },
      "commit": {
        "repaints": 1,
        "state": "fetch_failed",
        "title": "Commit not fetched · fetched 5 min ago",
        "detail": "This commit is not in the mirror, and it could not be fetched. The server did not answer.",
        "offer": "[Retry]"
      }
    },
    {
      "step": "the origin no longer shows the repository",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refresh failed · fetched 5 min ago",
        "tone": "warning",
        "detail": "The repository was not found, or it is private and could not be read. The pinned revision is still served from the mirror.",
        "offer": "topic is now at 92b31b078548 [Switch] → refs/remotes/origin/topic",
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
      "repaints": 1,
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
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
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
      "repaints": 1,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 6 d ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
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
      "repaints": 1,
      "paint": {
        "label": "Refresh failed · fetched 6 d ago",
        "tone": "warning",
        "detail": "The origin could not be read. The pinned revision is still served from the mirror.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
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
      "repaints": 1,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin. The mirror was last fetched 6 d ago.",
        "offer": "topic is now at 66f65bf1e89d [Switch] → refs/remotes/origin/topic",
        "error": null
      }
    }
  ],
  "guard": {
    "page": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb",
    "sent": [
      {
        "url": "/api/file?path=g1-UkVBRE1FLm1k",
        "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
      },
      {
        "url": "/api/source/status",
        "pin": null
      },
      {
        "url": "http://elsewhere.example/api/file",
        "pin": null
      },
      {
        "url": "/api/tree?depth=1",
        "pin": "42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
      }
    ],
    "answered": [
      200,
      200,
      200,
      409
    ],
    "reported": [
      "66f65bf1e89dd9fdaeccc5377b2a342aa3fd2531"
    ]
  },
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
