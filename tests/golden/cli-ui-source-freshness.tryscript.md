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
a typed stale state with a reload action, and keeps its rows when a later page is
refused as `pin_changed`, since the walk would be refused again and the row offers the
reload.

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

Back and forward bring a page back without asking the server for it, so it can name a
commit the server stopped serving after a pin switch.
On such a landing, and only then, the page asks the status route once and reloads if
another commit is served; a data request refused meanwhile says so sooner.
`landing` is that decision for each way a page arrives: `asked` counts status requests
and `reloads` reloads, never more than one.
`wired` loads the same module as the server writes it into a pin’s page and shows the
requests that reached the server (`+pin` when one named the page’s commit), the events
the page announced, and whether it reloaded.
A page that stayed open while another tab switched does not reload itself: the row
offers it.

When the queue of pull requests a reader asked for has no room for the attended one’s
refresh, the server refuses a refresh that would refresh only that one (`429`,
`too_many`). The page’s own ask says nothing of it, as the pull request’s page does, and
a reader’s press says why in the server’s words.
A commit’s fetch in that state fetches the mirror and answers `pull_refresh` `too_many`,
and since only that refresh brings a newer head of the pull request, the commit view
says it did not run rather than that the origin lacks the commit.

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
        "detail": "Fetching from the origin, last fetched 6 d ago.",
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
        "detail": "Fetching from the origin, last fetched 6 d ago.",
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
        "detail": "Fetching from the origin, last fetched 6 d ago.",
        "offer": null,
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
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin, last fetched 6 d ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a page shown again polls at once",
      "requests": [
        "GET /api/source/status If-None-Match: \"s2\""
      ],
      "timer": "fast",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin, last fetched 6 d ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the refresh moved the branch; the page follows it",
      "requests": [
        "GET /api/source/status If-None-Match: \"s2\"",
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/topic\",\"view\":\"/view/\"}"
      ],
      "timer": "ask",
      "reloads": 1,
      "repaints": 1,
      "paint": {
        "label": "Updating to topic…",
        "tone": "refreshing",
        "detail": "topic has moved, and this page follows it.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a page on a file the new commit lacks goes to the root",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/topic\",\"view\":\"/view/g1-R09ORS5tZA\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Updating to topic…",
        "tone": "refreshing",
        "detail": "topic has moved, and this page follows it.",
        "offer": null,
        "error": null
      },
      "navigated": [
        "/view/"
      ]
    },
    {
      "step": "a refused follow says why and offers a reload",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/topic\",\"view\":\"/view/\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 2,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload page]",
        "error": "Could not follow topic to its new commit."
      }
    },
    {
      "step": "a refused follow is not asked again on the next poll",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload page]",
        "error": "Could not follow topic to its new commit."
      }
    },
    {
      "step": "the reload a refused follow offers",
      "requests": [],
      "timer": "ask",
      "reloads": 1,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload page]",
        "error": "Could not follow topic to its new commit."
      }
    },
    {
      "step": "another tab switched the pin",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload page]",
        "error": null
      }
    },
    {
      "step": "reload after a switch elsewhere",
      "requests": [],
      "timer": "ask",
      "reloads": 1,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload page]",
        "error": null
      }
    },
    {
      "step": "switched before the first poll",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload page]",
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
        "detail": "The address this page was opened at opens once it is fetched.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the fetch brought the selection; the page goes to it",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload page]",
        "error": null
      },
      "navigated": [
        "/view/g1-UkVBRE1FLm1k#L1"
      ]
    },
    {
      "step": "a page goes to a selection once",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload page]",
        "error": null
      }
    },
    {
      "step": "the address is not on the origin",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Address not found · fetched 5 min ago",
        "tone": "warning",
        "detail": "The address this page was opened at is not on the origin, so the default branch is shown.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the address could not be fetched",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Address not fetched · fetched 5 min ago",
        "tone": "warning",
        "detail": "The address this page was opened at could not be fetched, so the default branch is shown.",
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
        "detail": "The address this page was opened at opens once it is fetched.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "inside the freshness window a missing commit starts no fetch",
      "requests": [],
      "timer": "ask",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "not_found",
        "title": "This commit was not found in the last fetch, 5 min ago.",
        "detail": "This commit is not in the mirror as last fetched.",
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
        "detail": "Fetching from the origin, last fetched 5 min ago.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "It opens when it arrives.",
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
        "detail": "Fetching from the origin, last fetched 5 min ago.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 0,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "It opens when it arrives.",
        "offer": null
      }
    },
    {
      "step": "the fetch brought the commit; it opens",
      "requests": [
        "GET /api/source/status If-None-Match: \"s2\"",
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/topic\",\"view\":\"/view/\"}",
        "GET /api/git/commit/92b31b0785485bd9eaa9619d198a779c2699295d"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 2,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload page]",
        "error": "The request to follow the branch failed."
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
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/topic\",\"view\":\"/view/\"}",
        "GET /api/git/commit/0123456789abcdef0123456789abcdef01234567"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 2,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload page]",
        "error": "The request to follow the branch failed."
      },
      "commit": {
        "repaints": 1,
        "state": "not_found",
        "title": "This commit was not found in the last fetch, 5 min ago.",
        "detail": "No branch or tag on the origin has this commit.",
        "offer": "[Retry]"
      }
    },
    {
      "step": "asking again failed; the view does not say not found",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/topic\",\"view\":\"/view/\"}",
        "GET /api/git/commit/92b31b0785485bd9eaa9619d198a779c2699295d"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 2,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": "The server now serves another revision [Reload page]",
        "error": "The request to follow the branch failed."
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
        "detail": "Fetching from the origin, last fetched 5 min ago.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "It opens when it arrives.",
        "offer": null
      }
    },
    {
      "step": "no fetch of the mirror ran, and the view does not say one did",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}",
        "GET /api/git/commit/0123456789abcdef0123456789abcdef01234567"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "not_found",
        "title": "This commit was not found in the last fetch, 5 min ago.",
        "detail": "This commit is not in the mirror as last fetched.",
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
        "detail": "Fetching from the origin, last fetched 6 d ago.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "It opens when it arrives.",
        "offer": null
      }
    },
    {
      "step": "the commit could not be fetched",
      "requests": [
        "GET /api/source/status",
        "GET /api/git/commit/0123456789abcdef0123456789abcdef01234567"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refresh failed · fetched 6 d ago",
        "tone": "warning",
        "detail": "The origin could not be read.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "fetch_failed",
        "title": "Could not fetch this commit; the last fetch was 6 d ago.",
        "detail": "The origin could not be read.",
        "offer": "[Retry]"
      }
    },
    {
      "step": "the reader left before the fetch ended",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refresh failed · fetched 6 d ago",
        "tone": "warning",
        "detail": "The origin could not be read.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 0,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "It opens when it arrives.",
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
        "detail": "Fetching from the origin, last fetched 5 min ago.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "pending",
        "title": "Fetching this commit…",
        "detail": "It opens when it arrives.",
        "offer": null
      }
    },
    {
      "step": "the queue had no room for the pull request's refresh",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}",
        "GET /api/git/commit/0123456789abcdef0123456789abcdef01234567"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "stale",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "fetch_failed",
        "title": "Could not fetch this commit; the last fetch was 5 min ago.",
        "detail": "Its pull request could not be refreshed while others are being fetched. Try again shortly.",
        "offer": "[Retry]"
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
        "detail": "Fetching from the origin, last fetched 5 min ago.",
        "offer": null,
        "error": "The server did not answer."
      },
      "commit": {
        "repaints": 1,
        "state": "fetch_failed",
        "title": "Could not fetch this commit; the last fetch was 5 min ago.",
        "detail": "This commit could not be fetched.",
        "offer": "[Retry]"
      }
    },
    {
      "step": "the origin no longer shows the repository",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refresh failed · fetched 5 min ago",
        "tone": "warning",
        "detail": "The repository was not found, or it is private and could not be read.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a refresh failed; the pin is still served",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refresh failed · fetched 5 min ago",
        "tone": "warning",
        "detail": "The origin could not be read.",
        "offer": null,
        "error": null
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
        "detail": "Fetching from the origin, last fetched 6 d ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a stale page whose refresh fails asks once",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refresh failed · fetched 6 d ago",
        "tone": "warning",
        "detail": "The origin could not be read.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "shown again, a stale page asks again",
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
        "detail": "Fetching from the origin, last fetched 6 d ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a page's own refresh with no room in the queue says nothing",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "stale",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a press with no room in the queue says why",
      "requests": [
        "POST /api/source/refresh {}"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "stale",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": "Other refreshes are running. Try again shortly."
      }
    }
  ],
  "guard": {
    "page": "66f65bf1e89dd9fdaeccc5377b2a342aa3fd2531",
    "sent": [
      {
        "url": "/api/file?path=g1-UkVBRE1FLm1k",
        "pin": "66f65bf1e89dd9fdaeccc5377b2a342aa3fd2531"
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
        "url": "/api/event-log/client",
        "pin": null
      },
      {
        "url": "/api/event-log?client=k3v9q2zx",
        "pin": null
      },
      {
        "url": "/api/event-logs",
        "pin": "66f65bf1e89dd9fdaeccc5377b2a342aa3fd2531"
      },
      {
        "url": "/api/tree?depth=1",
        "pin": "66f65bf1e89dd9fdaeccc5377b2a342aa3fd2531"
      }
    ],
    "answered": [
      200,
      200,
      200,
      200,
      200,
      200,
      409
    ],
    "reported": [
      "42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
    ]
  },
  "landing": [
    {
      "landing": "restored from the back/forward cache, nothing switched",
      "asked": 1,
      "reloads": 0
    },
    {
      "landing": "restored from the back/forward cache after a switch",
      "asked": 1,
      "reloads": 1
    },
    {
      "landing": "loaded from the HTTP cache by Back after a switch",
      "asked": 1,
      "reloads": 1
    },
    {
      "landing": "loaded by Back, nothing switched, another tab switches later",
      "asked": 1,
      "reloads": 0
    },
    {
      "landing": "an ordinary load whose data request is refused",
      "asked": 0,
      "reloads": 0
    },
    {
      "landing": "a reload, which is where a landing's reload ends",
      "asked": 0,
      "reloads": 0
    },
    {
      "landing": "restored after the server restarted on a folder",
      "asked": 1,
      "reloads": 1
    },
    {
      "landing": "restored while the server does not answer",
      "asked": 2,
      "reloads": 0
    }
  ],
  "wired": [
    {
      "page": "first load",
      "requests": [
        "GET /api/tree?depth=1 +pin"
      ],
      "events": [],
      "reloads": 0
    },
    {
      "page": "restored, nothing switched",
      "requests": [
        "GET /api/source/status"
      ],
      "events": [],
      "reloads": 0
    },
    {
      "page": "restored after a switch",
      "requests": [
        "GET /api/source/status"
      ],
      "events": [],
      "reloads": 1
    },
    {
      "page": "loaded from the HTTP cache by Back after a switch",
      "requests": [
        "GET /api/source/status",
        "GET /api/tree?depth=1 +pin"
      ],
      "events": [
        "metabrowser:pin-changed 42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
      ],
      "reloads": 1
    },
    {
      "page": "another tab switched while this one stayed open",
      "requests": [
        "GET /api/tree?depth=1 +pin"
      ],
      "events": [
        "metabrowser:pin-changed 42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
      ],
      "reloads": 0
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
      "failure": "another tab switched the revision",
      "status": 409,
      "code": "pin_changed",
      "initial": false,
      "means": "failed"
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
  ],
  "refreshNow": {
    "a fetch that runs: settled while it runs, then once it has ended": [
      false,
      true
    ],
    "a poll that fails while it runs: settled while it runs, then once it failed": [
      false,
      true
    ],
    "a row disposed while it runs: settled while it runs, then once disposed": [
      false,
      true
    ],
    "a refused refresh: settled at once": true
  }
}
? 0
```

## A Page’s Own Ask

A page on one of the origin’s branches makes its own ask while it is visible,
`POST /api/source/refresh` with `{"for": "page"}`, with its first status and then as
often as the status’s `probe_every_s` says (`ask` in the `timer` column).
The server asks the origin where the branch is and answers the status, so the ask is the
page’s poll too; a hidden page sends none.
A probe that finds a push starts the fetch at once, and the page polls quickly until it
ends and then follows its branch.

A fetch nobody asked for is quiet: the one the ask starts once a window, and the one a
server runs by itself while no page asks.
The status says so (`refresh_quiet`), and the row repaints nothing for it, so it keeps
its words and its button and announces nothing.
A server that refuses the ask is polled instead, one that stops answering is reported as
a failed poll is, and a page on a commit opened by its ID sends no ask.
A commit view that waits for the first status does not wait for the first ask, which the
server may hold for as long as a probe takes (`answeredBeforeTheAsk`).

```console
$ node tests/dom/source-freshness-session.js asks
{
  "part": "asks",
  "steps": [
    {
      "step": "a page on a branch asks with its first status",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "an unchanged branch: the ask is the poll, and nothing repaints",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a hidden page asks nothing",
      "requests": [],
      "timer": null,
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "shown again, the page asks at once",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the origin moved the branch: the fetch starts at once",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "fast",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin, last fetched 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the fetch brought the push; the page follows its branch",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/topic\",\"view\":\"/view/\"}"
      ],
      "timer": "ask",
      "reloads": 1,
      "repaints": 1,
      "paint": {
        "label": "Updating to topic…",
        "tone": "refreshing",
        "detail": "topic has moved, and this page follows it.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "once a window the mirror is fetched, and the row says nothing",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the quiet fetch ended, and the row still says nothing new",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a refused ask says nothing, and the page polls instead",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the poll after a refused ask",
      "requests": [
        "GET /api/source/status If-None-Match: \"s1\""
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the server stopped answering the page's asks",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": "The server did not answer."
      }
    },
    {
      "step": "a page on a commit sends no ask of its own",
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
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a page on a commit polls slowly",
      "requests": [
        "GET /api/source/status If-None-Match: \"s1\""
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the server's own fetch says nothing on a page that is open",
      "requests": [
        "GET /api/source/status If-None-Match: \"s1\""
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a missing commit does not wait for the page's first ask",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": null,
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 1,
        "state": "not_found",
        "title": "This commit was not found in the last fetch, 5 min ago.",
        "detail": "This commit is not in the mirror as last fetched.",
        "offer": "[Retry]"
      },
      "answeredBeforeTheAsk": true
    },
    {
      "step": "the page's first ask is answered afterwards",
      "requests": [],
      "timer": "ask",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Fetched 5 min ago",
        "tone": "quiet",
        "detail": "The mirror was last fetched from its origin 5 min ago.",
        "offer": null,
        "error": null
      },
      "commit": {
        "repaints": 0,
        "state": "not_found",
        "title": "This commit was not found in the last fetch, 5 min ago.",
        "detail": "This commit is not in the mirror as last fetched.",
        "offer": "[Retry]"
      }
    }
  ]
}
? 0
```

A repository folder that keeps a store of its checkout’s origin has the row on every
page, its working tree’s too.
What is fetched there is Metabrowser’s store of the origin, never the checkout, and the
row says so where a mirror’s says “mirror”.
A page that shows nothing of the store, the working tree’s or one of the checkout’s own
revisions, has a store grown old fetched by its own quiet ask, once: nothing on the page
can change when that fetch ends, so the row does not say “Refreshing…” for it.
The reader’s own Refresh does, and so does a page on one of the origin’s branches.
A fetch that failed says the checkout is unchanged.
The row offers no reload on a folder’s page: its ref selector does.
The statuses are a real folder’s, recorded in
`tests/fixtures/source-ref-selector-origin-responses.json` by
`tests/test_source_ref_selector_origin_session.py`.

```console
$ node tests/dom/source-freshness-session.js folder
{
  "part": "folder",
  "steps": [
    {
      "step": "the working tree's page, its origin's store grown old, asks quietly, once",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Origin fetched 6 d ago",
        "tone": "quiet",
        "detail": "The origin was last fetched 6 d ago, without changing the checkout.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the store was fetched; the row says when, and nothing reloads",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Origin fetched 5 d ago",
        "tone": "quiet",
        "detail": "The origin was last fetched 5 d ago, without changing the checkout.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the reader's own Refresh says so while it runs",
      "requests": [
        "POST /api/source/refresh {}"
      ],
      "timer": "fast",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refreshing…",
        "tone": "refreshing",
        "detail": "Fetching from the origin, last fetched 5 d ago.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a fetch that failed says the checkout is unchanged",
      "requests": [
        "GET /api/source/status"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Refresh failed · origin fetched 5 d ago",
        "tone": "warning",
        "detail": "The refresh failed.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "an origin branch's page names the store, not a mirror",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Origin fetched 5 d ago",
        "tone": "quiet",
        "detail": "The origin was last fetched 5 d ago, without changing the checkout.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the server shows the working tree again: this row offers no reload",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "slow",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Origin fetched 6 d ago",
        "tone": "quiet",
        "detail": "The origin was last fetched 6 d ago, without changing the checkout.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "an origin branch's page, its store grown old, asks loudly",
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
        "detail": "Fetching from the origin, last fetched 5 d ago.",
        "offer": null,
        "error": null
      }
    }
  ]
}
? 0
```

A repository folder’s page on one of the checkout’s own branches reads that branch, not
one commit of it, as a mirror’s page on a branch does.
Its status says how often to ask (`probe_every_s`), and the ask is the page’s own,
`{"for": "page"}`: for it the server reads where the branch is in the checkout, fetching
nothing, and serves the new commit when the reader’s commit or fetch moved it.
The page then asks the pin route for its ref with its own address and reloads there.
A folder with no store of an origin has nothing refreshable and so no row, and follows
all the same: the row is drawn only while the page goes to the new commit, or to say
that a follow was refused, which a press asks for again.
A hidden page asks nothing.
A branch the reader deletes while it is shown keeps its last commit served, and its
status’s `latest` is null: a quiet row says the branch no longer exists in the checkout
and the page shows its last commit, and with a store the store’s row says it too.
The answers are a real folder’s, from the same recording.

```console
$ node tests/dom/source-freshness-session.js checkout-branch
{
  "part": "checkout-branch",
  "steps": [
    {
      "step": "a page on the checkout's own branch asks where the branch is",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": {
        "label": "Origin fetched 5 d ago",
        "tone": "quiet",
        "detail": "The origin was last fetched 5 d ago, without changing the checkout.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the branch is where it was: nothing repaints, and it asks again",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 0,
      "paint": {
        "label": "Origin fetched 5 d ago",
        "tone": "quiet",
        "detail": "The origin was last fetched 5 d ago, without changing the checkout.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "the reader committed on the branch; the page follows it",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}",
        "POST /api/source/pin {\"ref\":\"refs/heads/trunk\",\"view\":\"/view/g1-bQ\"}"
      ],
      "timer": "ask",
      "reloads": 1,
      "repaints": 1,
      "paint": {
        "label": "Updating to trunk…",
        "tone": "refreshing",
        "detail": "trunk has moved, and this page follows it.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "with no store of an origin there is no row, and the page still asks",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 1,
      "paint": null
    },
    {
      "step": "a follow the server refused says the branch moved, and why",
      "requests": [
        "POST /api/source/refresh {\"for\":\"page\"}",
        "POST /api/source/pin {\"ref\":\"refs/heads/trunk\",\"view\":\"/view/g1-bQ\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 2,
      "paint": {
        "label": "trunk moved",
        "tone": "warning",
        "detail": "trunk has moved, and this page shows where it was.",
        "offer": null,
        "error": "Could not follow trunk to its new commit."
      }
    },
    {
      "step": "pressed, the page asks again and follows",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/heads/trunk\",\"view\":\"/view/g1-bQ\"}"
      ],
      "timer": "ask",
      "reloads": 1,
      "repaints": 1,
      "paint": {
        "label": "Updating to trunk…",
        "tone": "refreshing",
        "detail": "trunk has moved, and this page follows it.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "a hidden page asks nothing",
      "requests": [],
      "timer": null,
      "reloads": 0,
      "repaints": 0,
      "paint": null
    },
    {
      "step": "the reader deleted the branch: the row says its last commit stays",
      "requests": [
        "GET /api/source/status",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "timer": "ask",
      "reloads": 0,
      "repaints": 2,
      "paint": {
        "label": "topic no longer exists",
        "tone": "quiet",
        "detail": "topic no longer exists in this checkout; this page shows its last commit.",
        "offer": null,
        "error": null
      }
    },
    {
      "step": "with a store, the store's row says the branch is gone",
      "paint": {
        "label": "trunk no longer exists · origin fetched 5 d ago",
        "tone": "quiet",
        "detail": "trunk no longer exists in this checkout; this page shows its last commit."
      }
    }
  ]
}
? 0
```
