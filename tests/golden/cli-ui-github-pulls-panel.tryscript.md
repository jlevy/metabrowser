---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Pulls Panel

The Pulls tab defaults to Open, followed by Closed and All.
The exact repository total is separate from the selected filter’s total, cached catalog
progress, and displayed rows.
The visible panel watches the repository.
An admitted lightweight catalog job can finish in the background after the panel hides.
Opening the panel reads cache pages of 100 rows, the first 500 of them.
Scrolling within 240 pixels of the displayed tail requests another cache page, with no
end but the filter’s own, and can prioritize matching metadata that the background walk
has yet to cache. No notice says how many rows are held.
Below the last row, while a page is read or GitHub’s pages for the filter still arrive,
the navigation’s scan indicator shows its spinner and “~N pull requests fetched”.

A progress-only catalog update retains the displayed prefix and its row identity.
A changed generation stages the displayed range in bounded cache pages and accepts it
only when every page has the same source, reader, and generation.
Changing filters or hiding the panel aborts presentation reads, with late responses
unable to replace the next request’s ownership.
One connection row shows progress while no rows are shown, and otherwise the rows’ age,
breathing while a refresh runs, or recovery, with a Refresh action; nothing spins over
rows. A failed refresh keeps cached rows.

Holding a key changes two row marks per step and reads no detail until the walk stops.
Opening a PR can reuse the one cache-only record read made by a click, focus, or hover.
A row whose record is stale opens painted refreshing and refreshes it at once for a
click, after a wait for a key, and not until a held key is let go.
The production row mount keeps current and focused rows, text-only titles, absolute
accessibility positions, and bounded retained changed-file trees.
A variable-height spacer window bounds mounted rows as the displayed list grows.

This browserless session loads production code and replays the actual lifecycle,
cached-window, and changed-prefix recordings in `tests/fixtures/`.
`tests/test_github_pulls_panel_session.py` regenerates that recording through the real
application and verifies the paging, failure, ownership, and keyboard relations.
The clock, timers, and visibility are controlled so the transcript records behavior
without making a browser timing claim.

```console
$ node tests/dom/github-pulls-panel-session.js
{
  "steps": [
    {
      "step": "hidden: one cache read and no provider work",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "painted": 2,
      "paint": {
        "filter": "all",
        "status": "absent",
        "listName": "Pull requests of octo/demo",
        "summary": "octo/demo",
        "connection": {
          "state": "working",
          "text": "Fetching pull requests…",
          "canRefresh": false
        },
        "live": "Fetching pull requests…"
      }
    },
    {
      "step": "opening starts the all-history catalog job",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-1\"",
        "POST /api/plugin/github/pulls-refresh {\"state\":\"all\",\"target\":500}"
      ],
      "timer": "slow",
      "painted": 0,
      "paint": {
        "filter": "all",
        "status": "absent",
        "listName": "Pull requests of octo/demo",
        "summary": "octo/demo",
        "connection": {
          "state": "working",
          "text": "Fetching pull requests…",
          "canRefresh": false
        },
        "live": "Fetching pull requests…"
      }
    },
    {
      "step": "the catalog runs independently of the panel",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "timer": "fast",
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "pending",
        "listName": "Pull requests of octo/demo",
        "summary": "octo/demo",
        "connection": {
          "state": "working",
          "text": "Fetching pull requests…",
          "canRefresh": false
        },
        "live": "Fetching pull requests…"
      }
    },
    {
      "step": "the top cache page arrives",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-3\"",
        "GET /api/plugin/github/pulls?state=all&limit=100&after=9"
      ],
      "marks": [
        "anchor null -> 106"
      ],
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "current",
        "listName": "Pull requests of octo/demo: 102 pull requests",
        "summary": "102 PRs on octo/demo",
        "connection": {
          "state": "connected",
          "text": "Updated just now",
          "canRefresh": true
        },
        "live": "Pull requests of octo/demo: 102 pull requests",
        "rowsHeld": 100,
        "rows": [
          "[Open] Work item 106 | #106 · contributor | /pull/106",
          "[Open] Work item 105 | #105 · contributor | /pull/105",
          "…",
          "[Draft] WIP: draft the next page | #10 · maintainer | /pull/10",
          "[Closed] spam | #9 · ghost | /pull/9"
        ]
      }
    },
    {
      "step": "cached windows fill only the display budget",
      "requests": [
        "POST /api/plugin/github/pulls-prefetch {\"records\":[105,106,104,103,102],\"files\":[105],\"changed\":true}"
      ],
      "timer": "slow",
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "current",
        "listName": "Pull requests of octo/demo: 102 pull requests",
        "summary": "102 PRs on octo/demo",
        "connection": {
          "state": "connected",
          "text": "Updated just now",
          "canRefresh": true
        },
        "live": "Pull requests of octo/demo: 102 pull requests",
        "rowsHeld": 102,
        "rows": [
          "[Open] Work item 106 | #106 · contributor | /pull/106",
          "[Open] Work item 105 | #105 · contributor | /pull/105",
          "…",
          "[Merged] Say more in the guide | #8 · maintainer | /pull/8",
          "[Open] Count to two in the app | #7 · forker | /pull/7"
        ]
      }
    },
    {
      "step": "hidden: no presentation timer",
      "requests": [],
      "painted": 0
    },
    {
      "step": "reopening reads one tagged cache window",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-5\""
      ],
      "timer": "slow",
      "painted": 0
    },
    {
      "step": "Open has its exact matching count",
      "requests": [
        "GET /api/plugin/github/pulls?state=open&limit=100"
      ],
      "timer": "slow",
      "marks": [
        "anchor 106 -> null",
        "anchor null -> 106"
      ],
      "filterChanged": [
        "open"
      ],
      "painted": 2,
      "paint": {
        "filter": "open",
        "status": "current",
        "listName": "Pull requests of octo/demo: 100 pull requests",
        "summary": "102 PRs on octo/demo",
        "connection": {
          "state": "connected",
          "text": "Updated just now",
          "canRefresh": true
        },
        "live": "Pull requests of octo/demo: 100 pull requests",
        "rowsHeld": 100,
        "rows": [
          "[Open] Work item 106 | #106 · contributor | /pull/106",
          "[Open] Work item 105 | #105 · contributor | /pull/105",
          "…",
          "[Draft] WIP: draft the next page | #10 · maintainer | /pull/10",
          "[Open] Count to two in the app | #7 · forker | /pull/7"
        ]
      }
    },
    {
      "step": "leaving a filter aborts its read",
      "requests": [
        "GET /api/plugin/github/pulls?state=closed&limit=100",
        "aborted GET /api/plugin/github/pulls?state=closed&limit=100",
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-5\""
      ],
      "timer": "slow",
      "marks": [
        "anchor 106 -> null",
        "anchor null -> 106"
      ],
      "filterChanged": [
        "closed"
      ],
      "painted": 2
    },
    {
      "step": "500 shown while the catalog continues in the background",
      "requests": [
        "GET /api/plugin/github/pulls?state=closed&limit=100",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5901",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5801",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5701",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5601",
        "POST /api/plugin/github/pulls-refresh {\"state\":\"closed\",\"target\":500,\"background\":true}",
        "POST /api/plugin/github/pulls-prefetch {\"records\":[5999,6000,5998,5997,5996],\"files\":[5999],\"changed\":true}"
      ],
      "timer": "slow",
      "marks": [
        "anchor null -> 6000"
      ],
      "painted": 7,
      "paint": {
        "filter": "closed",
        "status": "current",
        "listName": "Pull requests of octo/demo: 1,000 pull requests",
        "summary": "1,000 PRs on octo/demo",
        "connection": {
          "state": "connected",
          "text": "Updated just now",
          "canRefresh": false,
          "refreshing": true
        },
        "live": "Pull requests of octo/demo: 1,000 pull requests",
        "rowsHeld": 500,
        "rows": [
          "[Closed] Work item 6000 | #6000 · contributor | /pull/6000",
          "[Closed] Work item 5999 | #5999 · contributor | /pull/5999",
          "…",
          "[Closed] Work item 5502 | #5502 · contributor | /pull/5502",
          "[Closed] Work item 5501 | #5501 · contributor | /pull/5501"
        ]
      }
    },
    {
      "step": "6,000 cached: the same 500 rows stay in place",
      "requests": [
        "GET /api/plugin/github/pulls?state=closed&limit=100"
      ],
      "timer": "fast",
      "painted": 1,
      "paint": {
        "filter": "closed",
        "status": "current",
        "listName": "Pull requests of octo/demo: 6,000 pull requests",
        "summary": "6,000 PRs on octo/demo",
        "connection": {
          "state": "connected",
          "text": "Updated just now",
          "canRefresh": false,
          "refreshing": true
        },
        "live": "Pull requests of octo/demo: 6,000 pull requests",
        "rowsHeld": 500,
        "rows": [
          "[Closed] Work item 6000 | #6000 · contributor | /pull/6000",
          "[Closed] Work item 5999 | #5999 · contributor | /pull/5999",
          "…",
          "[Closed] Work item 5502 | #5502 · contributor | /pull/5502",
          "[Closed] Work item 5501 | #5501 · contributor | /pull/5501"
        ]
      }
    },
    {
      "step": "nearing the tail reads the next cached page",
      "requests": [
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5501"
      ],
      "timer": "fast",
      "painted": 1,
      "paint": {
        "filter": "closed",
        "status": "current",
        "listName": "Pull requests of octo/demo: 6,000 pull requests",
        "summary": "6,000 PRs on octo/demo",
        "connection": {
          "state": "connected",
          "text": "Updated just now",
          "canRefresh": false,
          "refreshing": true
        },
        "progress": "Fetching pull requests…",
        "live": "Pull requests of octo/demo: 6,000 pull requests",
        "rowsHeld": 500,
        "rows": [
          "[Closed] Work item 6000 | #6000 · contributor | /pull/6000",
          "[Closed] Work item 5999 | #5999 · contributor | /pull/5999",
          "…",
          "[Closed] Work item 5502 | #5502 · contributor | /pull/5502",
          "[Closed] Work item 5501 | #5501 · contributor | /pull/5501"
        ]
      }
    },
    {
      "step": "scrolling to the tail five times reads 500 more cached rows without provider work",
      "requests": [
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5401",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5301",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5201",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5101"
      ],
      "timer": "fast",
      "painted": 9,
      "paint": {
        "filter": "closed",
        "status": "current",
        "listName": "Pull requests of octo/demo: 6,000 pull requests",
        "summary": "6,000 PRs on octo/demo",
        "connection": {
          "state": "connected",
          "text": "Updated just now",
          "canRefresh": false,
          "refreshing": true
        },
        "live": "Pull requests of octo/demo: 6,000 pull requests",
        "rowsHeld": 1000,
        "rows": [
          "[Closed] Work item 6000 | #6000 · contributor | /pull/6000",
          "[Closed] Work item 5999 | #5999 · contributor | /pull/5999",
          "…",
          "[Closed] Work item 5002 | #5002 · contributor | /pull/5002",
          "[Closed] Work item 5001 | #5001 · contributor | /pull/5001"
        ]
      }
    },
    {
      "step": "a new PR revalidates the display through ten bounded cache pages",
      "requests": [
        "GET /api/plugin/github/pulls?state=closed&limit=100 if-none-match \"pulls-36\"",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5902",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5802",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5702",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5602",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5502",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5402",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5302",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5202",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5102"
      ],
      "timer": "fast",
      "painted": 1,
      "paint": {
        "filter": "closed",
        "status": "current",
        "listName": "Pull requests of octo/demo: 6,001 pull requests",
        "summary": "6,001 PRs on octo/demo",
        "connection": {
          "state": "connected",
          "text": "Updated just now",
          "canRefresh": false,
          "refreshing": true
        },
        "live": "Pull requests of octo/demo: 6,001 pull requests",
        "rowsHeld": 1000,
        "rows": [
          "[Closed] Work item 6001 | #6001 · contributor | /pull/6001",
          "[Closed] Work item 6000 | #6000 · contributor | /pull/6000",
          "…",
          "[Closed] Work item 5003 | #5003 · contributor | /pull/5003",
          "[Closed] Work item 5002 | #5002 · contributor | /pull/5002"
        ]
      }
    },
    {
      "step": "Up at the first row is clamped",
      "requests": [],
      "timer": "slow",
      "painted": 0
    },
    {
      "step": "one press opens with its cached record",
      "requests": [
        "GET /api/plugin/github/pull?number=105",
        "POST /api/plugin/github/pulls-prefetch {\"records\":[106,104,103,102],\"files\":[105,106,104],\"changed\":false}"
      ],
      "timer": "slow",
      "marks": [
        "anchor 106 -> 105 focus",
        "current null -> 105"
      ],
      "opened": [
        {
          "number": 105,
          "tab": "",
          "history": "replace",
          "fetchAfterMs": 500,
          "initial": "the record read for it"
        }
      ],
      "painted": 0
    },
    {
      "step": "a key held for 40 rows",
      "requests": [],
      "timer": "slow",
      "marks": 80,
      "painted": 0
    },
    {
      "step": "the key is let go",
      "requests": [
        "GET /api/plugin/github/pull?number=65"
      ],
      "timer": "slow",
      "painted": 0
    },
    {
      "step": "the row it stopped on opens",
      "requests": [
        "POST /api/plugin/github/pulls-prefetch {\"records\":[66,64,106,105,104,103,102],\"files\":[65,66,64],\"changed\":false}"
      ],
      "timer": "slow",
      "opened": [
        {
          "number": 65,
          "tab": "",
          "history": "replace",
          "fetchAfterMs": 500,
          "initial": "the record read for it"
        }
      ],
      "painted": 0
    },
    {
      "step": "Back wins over a pending row opening",
      "requests": [
        "GET /api/plugin/github/pull?number=64"
      ],
      "timer": "slow",
      "marks": [
        "anchor 65 -> 64 focus",
        "current 65 -> 64",
        "current 64 -> 70",
        "anchor 64 -> 70"
      ],
      "reveals": [
        70
      ],
      "painted": 0
    },
    {
      "step": "a repeated hover and click reuse one cached record",
      "requests": [
        "GET /api/plugin/github/pull?number=80",
        "POST /api/plugin/github/pulls-prefetch {\"records\":[81,79,106,105,104,103,102],\"files\":[80,81,79],\"changed\":false}"
      ],
      "timer": "slow",
      "marks": [
        "current 70 -> 80",
        "anchor 70 -> 80"
      ],
      "opened": [
        {
          "number": 80,
          "tab": "",
          "history": "push",
          "fetchAfterMs": 0,
          "initial": "the record read for it"
        }
      ],
      "painted": 0
    },
    {
      "step": "a server with no GitHub repository",
      "requests": [
        "GET /api/plugin/github/pulls?state=open&limit=100"
      ],
      "timer": "slow",
      "painted": 2,
      "paint": {
        "filter": "open",
        "status": "absent",
        "listName": "Pull requests",
        "empty": "This server serves no GitHub repository.",
        "live": "This server serves no GitHub repository."
      }
    },
    {
      "step": "a checkout whose origin cannot be listed",
      "requests": [
        "GET /api/plugin/github/pulls?state=open&limit=100"
      ],
      "timer": "slow",
      "painted": 2,
      "paint": {
        "filter": "open",
        "status": "absent",
        "listName": "Pull requests",
        "empty": "This checkout’s origin is not a GitHub repository Metabrowser can list.",
        "live": "This checkout’s origin is not a GitHub repository Metabrowser can list."
      }
    },
    {
      "step": "dispose aborts presentation reads",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100",
        "aborted GET /api/plugin/github/pulls?state=all&limit=100"
      ],
      "painted": 1,
      "timers": []
    }
  ]
}
? 0
```

The remaining scenarios print as a second command.
`failures` pins the typed refresh outcomes.
The landing pane gives the neutral selection instruction while the list owns status.
`reader` follows a selected PR through its cache-only read and explicit detail fetch.
`paint` checks tree roles, absolute positions, numeric-only emphasis, text-only titles,
cached append behavior, and changed-file tree retention.
Given the shell’s toolbar slot and the band under it, the filters fill the slot, the
count and connection lines fill the band, outside the list’s scroller, and a disposed
list leaves both empty.
`numbers` runs the production shortcut registry and plugin facade around the panel: the
Open, Closed, and All chips and Refresh take `1` to `4` in reading order, before the
page’s numbered link, and each number asks for what its control’s click asks for.
A hidden or disposed panel’s controls give up their numbers.

```console
$ node tests/dom/github-pulls-panel-second-session.js
{
  "provider_calls": {
    "source acquisition": [
      "gh auth status",
      "gh api repos/octo/demo --jq .size"
    ],
    "cold cache reads": [],
    "catalog backfill": [
      "gh api user",
      "gh api graphql catalog state=all cursor=start",
      "gh api graphql catalog state=all cursor=all-100"
    ],
    "cached windows, filters, scrolling and reopen": [
      "gh api repos/octo/demo/issues?state=all&sort=updated&direction=desc&per_page=1"
    ],
    "due metadata refresh": [
      "gh api user (If-None-Match)",
      "gh api graphql catalog state=updated cursor=start"
    ],
    "fresh cached revisit": [],
    "list probes": [
      "gh api repos/octo/demo/issues?state=all&sort=updated&direction=desc&per_page=1 (If-None-Match)",
      "gh api repos/octo/demo/issues?state=all&sort=updated&direction=desc&per_page=1 (If-None-Match)",
      "gh api user (If-None-Match)",
      "gh api graphql catalog state=updated cursor=start"
    ],
    "refused newer_cache": [],
    "refused unknown_cache": []
  },
  "failures": {
    "newer_cache": {
      "status": "absent",
      "connection": {
        "text": "Could not refresh the list.",
        "state": "paused",
        "canRefresh": true
      }
    },
    "unknown_cache": {
      "status": "absent",
      "connection": {
        "text": "Could not refresh the list.",
        "state": "paused",
        "canRefresh": true
      }
    },
    "not_logged_in": {
      "status": "current",
      "connection": {
        "text": "Run gh auth login --hostname github.com to sign in to GitHub. Showing the pull requests last loaded.",
        "state": "paused",
        "canRefresh": true
      }
    },
    "gh_too_old": {
      "status": "current",
      "connection": {
        "text": "GitHub CLI needs an update. Showing the pull requests last loaded.",
        "help": "update",
        "state": "paused",
        "canRefresh": true
      }
    },
    "not_found_or_private": {
      "status": "current",
      "connection": {
        "text": "GitHub could not find this repository or grant access to it. Showing the pull requests last loaded.",
        "state": "paused",
        "canRefresh": true
      }
    },
    "network_error": {
      "status": "current",
      "connection": {
        "text": "Could not reach GitHub. Showing the pull requests last loaded.",
        "state": "paused",
        "canRefresh": true
      }
    },
    "gh_failed": {
      "status": "current",
      "connection": {
        "text": "Could not refresh the list. Showing the pull requests last loaded.",
        "state": "paused",
        "canRefresh": true
      }
    },
    "account_changed": {
      "status": "stale",
      "connection": {
        "text": "Could not refresh the list. Showing the pull requests last loaded.",
        "state": "paused",
        "canRefresh": true
      }
    },
    "gh_missing": {
      "status": "current",
      "connection": {
        "text": "GitHub CLI is not installed. Showing the pull requests last loaded.",
        "help": "install",
        "state": "paused",
        "canRefresh": true
      }
    },
    "cache_unwritable": {
      "status": "current",
      "connection": {
        "text": "Could not refresh the list. Showing the pull requests last loaded.",
        "state": "paused",
        "canRefresh": true
      }
    },
    "rate_limited": {
      "status": "current",
      "connection": {
        "text": "GitHub rate limit reached. Next attempt after 2026-09-18T00:00:00.000Z. Showing the pull requests last loaded.",
        "state": "paused",
        "canRefresh": false
      }
    }
  },
  "hostile": {
    "number": 7,
    "href": "/pull/7",
    "state": "merged",
    "stateLabel": "Merged",
    "title": "<img src=x onerror=\"alert(1)\"> & \"quotes\"",
    "author": "ghost",
    "avatar": null,
    "updatedAt": "2026-09-17T12:00:00Z",
    "meta": "#7 · ghost",
    "head": null
  },
  "probes": [
    {
      "step": "a current list is shown: its first probe ask is due at once",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100",
        "GET /api/plugin/github/pulls?state=all&limit=100&after=9",
        "POST /api/plugin/github/pulls-prefetch {\"records\":[105,106,104,103,102],\"files\":[105],\"changed\":true}"
      ],
      "poll": "slow",
      "probeInMs": 0,
      "firstRow": "Work item 106"
    },
    {
      "step": "the ask is sent",
      "requests": [
        "POST /api/plugin/github/pulls-refresh {\"state\":\"all\",\"target\":500,\"background\":true}"
      ],
      "poll": "slow",
      "probeInMs": null,
      "firstRow": "Work item 106"
    },
    {
      "step": "GitHub has nothing new: nothing is read, and the next ask waits an interval",
      "requests": [],
      "poll": "slow",
      "probeInMs": 10000,
      "firstRow": "Work item 106"
    },
    {
      "step": "the next ask finds a change, and its scan starts: the poll turns fast",
      "requests": [
        "POST /api/plugin/github/pulls-refresh {\"state\":\"all\",\"target\":500,\"background\":true}"
      ],
      "poll": "fast",
      "probeInMs": 10000,
      "firstRow": "Work item 106"
    },
    {
      "step": "an ask due while that scan runs is not sent, and the next waits an interval",
      "requests": [],
      "poll": "fast",
      "probeInMs": 10000,
      "firstRow": "Work item 106"
    },
    {
      "step": "the scan's rows are read",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100",
        "GET /api/plugin/github/pulls?state=all&limit=2&after=9",
        "POST /api/plugin/github/pulls-prefetch {\"records\":[105,106,104,103,102],\"files\":[105],\"changed\":true}"
      ],
      "poll": "slow",
      "probeInMs": 0,
      "firstRow": "Retitled between scans"
    },
    {
      "step": "hidden: no timer waits to ask",
      "requests": [],
      "poll": null,
      "probeInMs": null,
      "firstRow": "Retitled between scans"
    },
    {
      "step": "visible again a minute later: the list is read, and a probe ask is due at once",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-12\""
      ],
      "poll": "slow",
      "probeInMs": 0,
      "firstRow": "Retitled between scans"
    },
    {
      "step": "the tab is not shown: no timer waits to ask",
      "requests": [],
      "poll": null,
      "probeInMs": null,
      "firstRow": "Retitled between scans"
    },
    {
      "step": "pause while the next ask waits 10000 ms: no timer waits to ask",
      "probeInMs": null
    },
    {
      "step": "dispose while the next ask waits 10000 ms: no timer waits to ask",
      "probeInMs": null
    }
  ],
  "reader": [
    {
      "name": "a visible cold direct link fills the cache",
      "asked": [
        "GET /api/plugin/github/pull?number=7",
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"wait_core\":true}"
      ],
      "waits": [
        30000,
        0
      ],
      "before": {
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "revalidating": false
      },
      "after": {
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "revalidating": false
      }
    },
    {
      "name": "a click on a row with no record fetches it at once",
      "asked": [
        "GET /api/plugin/github/pull?number=7",
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"wait_core\":true}"
      ],
      "waits": [
        30000,
        0
      ],
      "before": {
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "revalidating": false
      },
      "after": {
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "revalidating": false
      }
    },
    {
      "name": "a key stopping on one waits, so tapping past it spends nothing",
      "asked": [
        "GET /api/plugin/github/pull?number=7",
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"wait_core\":true}"
      ],
      "waits": [
        30000,
        500
      ],
      "before": {
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "revalidating": false
      },
      "after": {
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "revalidating": false
      }
    },
    {
      "name": "a key still held waits out the page it opened, however long: it fetches nothing",
      "asked": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "waits": [
        30000,
        500
      ],
      "before": {
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "revalidating": false
      },
      "after": {
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "revalidating": false
      },
      "once let go": {
        "asked": [
          "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"wait_core\":true}"
        ],
        "message": "Fetching the pull request…",
        "revalidating": false
      }
    },
    {
      "name": "past the bound on jobs it says why, and offers Fetch",
      "asked": [
        "GET /api/plugin/github/pull?number=7",
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"wait_core\":true}"
      ],
      "waits": [
        30000,
        0
      ],
      "before": {
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "revalidating": false
      },
      "after": {
        "message": "The refresh could not start while other pull requests are being fetched.",
        "canRefresh": true,
        "revalidating": false
      }
    },
    {
      "name": "a row with a current record is probed at once, and an unchanged probe fetches nothing",
      "asked": [
        "GET /api/plugin/github/pull?number=7",
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"07eb0c3ec47a9c84c4d0b69ddfca32245cdede7023567fa7d179789783e8d66b\"}"
      ],
      "waits": [
        0,
        30000
      ],
      "before": {
        "message": null,
        "canRefresh": false,
        "revalidating": false
      },
      "after": {
        "message": null,
        "canRefresh": false,
        "revalidating": false
      }
    },
    {
      "name": "a click on a row whose record is stale refreshes it at once",
      "asked": [
        "GET /api/plugin/github/pull?number=7",
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"07eb0c3ec47a9c84c4d0b69ddfca32245cdede7023567fa7d179789783e8d66b\"}"
      ],
      "waits": [
        0,
        30000
      ],
      "before": {
        "message": null,
        "canRefresh": false,
        "revalidating": true
      },
      "after": {
        "message": null,
        "canRefresh": false,
        "revalidating": true
      }
    },
    {
      "name": "a key stopping on a stale row refreshes it after the wait",
      "asked": [
        "GET /api/plugin/github/pull?number=7",
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"07eb0c3ec47a9c84c4d0b69ddfca32245cdede7023567fa7d179789783e8d66b\"}"
      ],
      "waits": [
        500,
        30000
      ],
      "before": {
        "message": null,
        "canRefresh": false,
        "revalidating": true
      },
      "after": {
        "message": null,
        "canRefresh": false,
        "revalidating": true
      }
    },
    {
      "name": "a key still held over a stale row refreshes nothing until it is let go",
      "asked": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "waits": [
        500,
        30000
      ],
      "before": {
        "message": null,
        "canRefresh": false,
        "revalidating": true
      },
      "after": {
        "message": null,
        "canRefresh": false,
        "revalidating": true
      },
      "once let go": {
        "asked": [
          "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"07eb0c3ec47a9c84c4d0b69ddfca32245cdede7023567fa7d179789783e8d66b\"}"
        ],
        "message": null,
        "revalidating": true
      }
    }
  ],
  "paint": {
    "loading status": "Fetching pull requests…",
    "lent to the one Refresh": [
      "page",
      "pulls"
    ],
    "the list's part while the list loads": "asks nothing",
    "landing": "Select a pull request.",
    "filter tallies": [
      "Open 100",
      "Closed 2",
      "All 102"
    ],
    "only the repository name is bold": [
      {
        "node": "SPAN",
        "text": "102"
      },
      {
        "node": "#text",
        "text": " PRs on "
      },
      {
        "node": "STRONG",
        "text": "octo/demo"
      }
    ],
    "the list": "ul .github-pulls-list role=\"tree\" aria-label=\"Pull requests of octo/demo: 102 pull requests\"",
    "a row": [
      "li .github-pulls-item role=\"none\"",
      "a .github-pulls-row href=\"/pull/106\" role=\"treeitem\" aria-level=\"1\" aria-expanded=\"false\" aria-describedby=\"github-pull-change-106\" tabindex=\"-1\" aria-posinset=\"1\" aria-setsize=\"102\""
    ],
    "the row whose page is shown": "a .github-pulls-row.selected href=\"/pull/105\" role=\"treeitem\" aria-level=\"1\" aria-expanded=\"true\" aria-describedby=\"github-pull-change-105\" tabindex=\"0\" aria-current=\"page\" aria-selected=\"true\" aria-posinset=\"2\" aria-setsize=\"102\" aria-owns=\"github-pull-files-105\"",
    "its parts": [
      "span .github-pulls-heading",
      "span .github-pulls-tail",
      "span .sr-only"
    ],
    "its text leads with its title": true,
    "a PR preview leaves its files expanded": false,
    "Right on its row opens its cached changed files": "/api/plugin/github/pull-files?number=105&offset=0",
    "they hang under its item as a group": [
      "div .github-pulls-entry",
      "div .tree-children.github-pull-files role=\"group\" id=\"github-pull-files-105\" aria-label=\"Changed files of #105: 2 files\""
    ],
    "its row owns them, and its toggle, hidden, only turns its chevron": [
      "a .github-pulls-row.selected href=\"/pull/105\" role=\"treeitem\" aria-level=\"1\" aria-expanded=\"true\" aria-describedby=\"github-pull-change-105\" tabindex=\"0\" aria-current=\"page\" aria-selected=\"true\" aria-posinset=\"2\" aria-setsize=\"102\" aria-owns=\"github-pull-files-105\"",
      "span .github-pulls-change.disclosure-toggle.expanded aria-hidden=\"true\""
    ],
    "a title written as markup is one text node": [
      {
        "node": "#text",
        "data": "<img src=x onerror=\"alert(1)\"> & <b>bold</b>"
      }
    ],
    "rows built for the first window": 100,
    "a cached window of 2 auto-fills the budget: rows built, aged, keyed": [
      2,
      2,
      102
    ],
    "rows held": 102,
    "an age, before": "2h",
    "an age, two hours on": "4h",
    "rows built to tell it": 0,
    "a passive retry over cached rows breathes the announced outage, with no spinner": "Could not reach GitHub. Showing the pull requests last loaded.",
    "closing twelve expanded trees enforces retention immediately": {
      "whileExpanded": 10,
      "afterClosingAll": 9
    },
    "disposed: what is left in the tab": 0,
    "with the host's toolbar and band: what each holds": {
      "toolbar": [
        "github-pulls-filters"
      ],
      "band": [
        "github-pulls-status",
        "github-pulls-connection"
      ],
      "tab": [
        "github-pulls-list",
        "github-pulls-empty"
      ]
    },
    "with the host's toolbar and band: what each holds once disposed": {
      "toolbar": 0,
      "band": 0,
      "tab": 0
    }
  },
  "numbers": {
    "the Pulls tab, loading": [
      "1 Refresh",
      "2 Open",
      "3 Closed",
      "4 All",
      "5 Browse code"
    ],
    "Refresh while the list loads": [
      {
        "what": "press 1",
        "handled": true
      },
      {
        "what": "click Refresh"
      }
    ],
    "the Pulls tab, settled": [
      "1 Refresh",
      "2 Open",
      "3 Closed",
      "4 All",
      "5 Browse code"
    ],
    "Refresh": [
      {
        "what": "press 1",
        "handled": true,
        "asked": [
          "POST /api/plugin/github/pulls-refresh {\"state\":\"all\",\"target\":500,\"retry\":true}"
        ]
      },
      {
        "what": "click Refresh",
        "asked": [
          "POST /api/plugin/github/pulls-refresh {\"state\":\"all\",\"target\":500,\"retry\":true}"
        ]
      }
    ],
    "the button while the list's refresh is on its way, then once it is answered": [
      "true",
      null
    ],
    "the state chips": [
      {
        "what": "press 2",
        "handled": true,
        "asked": [
          "GET /api/plugin/github/pulls?state=open&limit=100"
        ],
        "list": "open",
        "focused": "Open"
      },
      {
        "what": "press 3",
        "handled": true,
        "asked": [
          "GET /api/plugin/github/pulls?state=closed&limit=100"
        ],
        "list": "closed",
        "focused": "Closed"
      },
      {
        "what": "press 4",
        "handled": true,
        "asked": [
          "GET /api/plugin/github/pulls?state=all&limit=100"
        ],
        "list": "all",
        "focused": "All"
      },
      {
        "what": "click Open",
        "asked": [
          "GET /api/plugin/github/pulls?state=open&limit=100"
        ],
        "list": "open"
      },
      {
        "what": "click Closed",
        "asked": [
          "GET /api/plugin/github/pulls?state=closed&limit=100"
        ],
        "list": "closed"
      },
      {
        "what": "click All",
        "asked": [
          "GET /api/plugin/github/pulls?state=all&limit=100"
        ],
        "list": "all"
      },
      {
        "what": "press 4",
        "handled": true
      },
      {
        "what": "click All"
      }
    ],
    "the keycaps while Shift is held": "Refresh 1, Open 2, Closed 3, All 4, Modified within none, File type none, Browse code 5",
    "the Files tab": [
      "1 Refresh",
      "2 Modified within",
      "3 File type",
      "4 Browse code"
    ],
    "on the Files tab": [
      {
        "what": "press 2",
        "handled": true,
        "ran": [
          "Modified within"
        ]
      },
      {
        "what": "press 4",
        "handled": true,
        "ran": [
          "Browse code"
        ]
      },
      {
        "what": "press 5",
        "handled": false
      }
    ],
    "Refresh behind the Files tab": {
      "what": "press 1",
      "handled": true,
      "asked": [
        "POST /api/plugin/github/pulls-refresh {\"state\":\"all\",\"target\":500,\"retry\":true}"
      ],
      "then the list's catalog job": "asked"
    },
    "the Pulls tab, disposed": [
      "1 Refresh",
      "2 Browse code"
    ],
    "after disposal": [
      {
        "what": "press 2",
        "handled": true,
        "ran": [
          "Browse code"
        ]
      },
      {
        "what": "press 3",
        "handled": false
      }
    ],
    "the Files tab, after disposal": [
      "1 Refresh",
      "2 Modified within",
      "3 File type",
      "4 Browse code"
    ]
  }
}
? 0
```

## Optional Native Stack Navigation and Cold Loading

One shared snapshot retains verified memberships through refresh failure, keeps multiple
memberships, and refuses another source or reader.
Disposing the last consumer aborts its presentation reads; a late result cannot
overwrite a new owner.

```console
$ node tests/dom/github-pull-stacks-behavior.js
{"rowCaptions":{"single":{"text":"2/3","hint":"Stack #286, position 2 of 3","parts":[{"position":"2/3","stack":null}]},"shared":{"text":"3/3 · 900 1/2","hint":"Stack #286, position 3 of 3; Stack #900, position 1 of 2","parts":[{"position":"3/3","stack":null},{"position":"1/2","stack":900}]},"foreign":null},"authoritativeMembership":true,"multipleStacks":true,"identityGuard":true,"tabAndReaderIntent":true,"sharedRead":true,"failureRetention":true,"retryWindow":true,"disposal":true,"lateOwnerGuard":true,"initialFailureRetry":true}
? 0
```

The mounted PR page uses a shared gray skeleton only while cold or pending.
Cached refreshes stay readable.
Native stack members are created on disclosure; Previous PR and Next PR preserve the
active tab, clear file selection, and carry a reader’s explicit fetch intent.
An identity-only response removes the old source’s enrichment.
A member the Pulls list no longer holds in the state it said is drawn with its state
icon’s slot empty, not that state, and the page notes its own fresher record back over
the list’s older word.

```console
$ node tests/dom/github-pull-stack-mount-behavior.js
{"coldSkeleton":true,"pendingSkeleton":true,"cachedRefreshRetained":true,"authoritativeStack":true,"orderedNeighbors":true,"stackActivationFocus":true,"tabPreserved":true,"fileCleared":true,"explicitReaderIntent":true,"disposedWorkReleased":true,"memberStateTakenBack":true,"recordNotedBack":true}
? 0
```

## Active Page Selection and Retained Tree Cursors

The real page host opens the next PR and handles Back while the production panel holds
both file trees. Leaving clears the old page’s blue file selection while its manual
expansion and roving keyboard anchor remain.
A repeated route notification replays the active page’s observation; delayed or
unsubscribed old callbacks cannot repaint another page.
An explicit file keeps its selection through a temporarily unavailable jump.

```console
$ node tests/dom/github-pulls-file-selection-session.js
{
  "selection": {
    "observations": {
      "initial": [
        "/pull/105/files/src/app.txt"
      ],
      "repeat": [
        "/pull/105/files/src/app.txt"
      ],
      "leaving": [],
      "ignoredOld": [],
      "arriving": [
        "/pull/106/files/src/app.txt"
      ],
      "sameHandle": [
        "/pull/106/files/src/app.txt"
      ],
      "explicit": [
        "/pull/106/files/docs/new.md"
      ],
      "unavailable": [
        "/pull/106/files/docs/new.md"
      ],
      "reported": [
        "/pull/106/files/docs/new.md"
      ],
      "history": [
        "/pull/105/files/src/app.txt"
      ],
      "lateAfterHistory": []
    },
    "back": "mount",
    "readerExpansionRetained": true,
    "rovingAnchorRetained": true,
    "disposed": 0
  }
}
? 0
```

## Test: Prepare the Visible Pulls Window

The mounted panel requests preparation for visible rows and releases its window when it
hides. The session checks that a prepared description keeps its reader and observation
time. `titleBreathing` is which rows’ titles breathe: those of an admitted batch GitHub
is being read for, until a settled receipt, a new window, or going offline ends it; no
row is marked busy, and `beat` is the one start time the breaths are aligned to.

```console
$ node tests/dom/github-pulls-viewport-behavior.js
{"case":"viewport-height-increase","before":43,"after":78,"observedRoot":1,"gapStartsAt":null,"viewportHeight":3000,"oneVisibleFlash":true,"retainedReadingPlace":true,"titleBreathing":{"admitted":{"asked":[454,453,452,451],"breathing":[454,453,452,451],"busyRows":0},"settled":[],"moved":{"asked":[404,403,402],"breathing":[404,403,402]},"offline":[],"beat":[100,100,50,100]}}
? 0
```

## Test: Page Near the Pulls Tail

The controller adds one page on a near-tail signal and keeps selection in place.
Nothing caps it: approaches read past 500, 600, and 1,000 rows to the filter’s last row.
A reader parked at the tail keeps reading as GitHub’s pages land, under the scan
indicator, which leaves with the last row.
It stops at the actual filter tail and reads cached rows after a provider failure.
A late page cannot change the newly selected filter or consume its reconnect hint.
Offline, rate limits, focus, external setup recovery, and Refresh all use the same watch
controller.

```console
$ node tests/dom/github-pulls-catalog-behavior.js
{
  "defaultFilter": "open",
  "initialRows": 500,
  "rateHeldScrollRows": 1000,
  "scrollRows": 600,
  "terminalRows": 645,
  "uncappedScrollRows": 2500,
  "parkedTailRows": 2000,
  "countNotices": 0,
  "repeatedScrollSharesRequest": true,
  "keepsSelection": true,
  "cachedGrowthKeepsEveryRow": true,
  "failedProviderUsesCacheOnly": true,
  "hiddenTailIsIdle": true,
  "staleTailCannotChangeFilter": true,
  "progressOnlyReads": 1,
  "generationPages": 10,
  "detailReads": 0,
  "priorityTarget": 600,
  "lateWindowRejected": true,
  "ownerTransferred": true,
  "mixedGenerationRejected": true,
  "lateFilterRejected": true,
  "failedWindowDoesNotSpin": true,
  "newerRefreshKeepsOwnership": true,
  "freshPartialCatalogResumes": true,
  "offlineKeepsCache": true,
  "reconnectUsesBackgroundHint": true,
  "interactiveFilterKeepsPriority": true,
  "directAndHistoryFiltersKeepPriority": true,
  "hiddenWarmupYieldsToVisibleDemand": true,
  "acceptedTopArrivalsAreOneShot": true,
  "transientRetriesAutomatically": true,
  "retryKeepsPriorFailure": true,
  "localReadFailureDoesNotPost": true,
  "setupUsesQuietProbe": true,
  "focusCoalesces": true,
  "parkAndResume": true,
  "rateResetWake": true,
  "reloadCoalesces": true,
  "abortedTailKeepsWake": true
}
? 0
```

## Background PR Metadata Preparation

The production controller warms catalog metadata after startup, including while Files is
selected. The whole measured viewport has priority over the remaining catalog.
Eight is a transport batch size.
A completed pass stops, ordinary busy work backs off without abandoning demand, and
reconnect keeps its settled cursor.
A batch left unanswered twice is passed over and revisited after the pass, never before
its own 30 s, even when failures are staggered.
A visible demand aborts the background batch on its way, as disposal, a pause, or a
hidden page does before releasing its token, and each lane waits out a 6.5 s answer.
A held batch whose rate limit has already reset backs off as any other hold does, and
waits once for a reset still ahead.
These virtual-clock values describe scheduler behavior, not browser paint latency.

```console
$ node tests/dom/github-pr-prefetch-behavior.js
{"catalogRows":24,"settledOwnershipReleases":3,"prefixOwnership":{"retained":3,"revoked":4},"latePassReceipts":["ready","partial","failed","busy","not_owner","invalid"],"hiddenBatches":[8,8,8],"busyAttemptsMs":[0,1000,3000,7000],"allVisibleReadyMs":12000,"recoveredAfterLongBusyMs":91000,"cachedAfterColdStart":24,"recoveredRaceAndRevision":[24,25],"recoveredTransientAndPartial":[24,24],"cachedPastPartialCohort":24,"cachedAfterReconnect":24,"completedBeforeDisconnect":8,"backgroundRequestsAfterCompletion":17,"passedOver":{"cached":16,"atMs":7000,"attempts":["open@3000","open@4000","all@9000","all@10000","all@41000"]},"preemption":{"visibleSentAfterMs":0,"backgroundAbortedAfterMs":0},"slowCoveredMs":51500,"giveUpMs":{"visible":10000,"background":30000},"tornDown":[{"exit":"dispose","abortedAfterMs":0,"released":1},{"exit":"pause","abortedAfterMs":0,"released":1},{"exit":"hide","abortedAfterMs":0,"released":1}],"staggeredFailures":[2,11,10],"heldBackoff":{"none":{"asks":8,"gapsMs":[1000,2000,4000,8000,16000,30000,30000]},"lapsedRateLimit":{"asks":8,"gapsMs":[1000,2000,4000,8000,16000,30000,30000]},"staleNetworkError":{"asks":8,"gapsMs":[1000,2000,4000,8000,16000,30000,30000]},"rateLimitAhead":{"asks":6,"gapsMs":[59000,2000,4000,8000,16000]}}}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

## A Selection Reads Its Record Once

A click reads the selected record once.
The production Pulls controller opens the production page controller, which joins the
read the row’s peek started (`slowRead`) or takes an answer it gave within a fast poll
(`fastRead`); the pointer resting on the clicked row reads nothing more.
A record read ahead long before the click is read again with its tag (`oldReadAhead`).
Another row’s peek does not take the joined read from the page (`hoverAway`), and a read
handed to a page ends with that page when another replaces it (`superseded`).

```console
$ node tests/dom/github-pull-selection-read-behavior.js
{
  "slowRead": [
    "panel"
  ],
  "fastRead": [
    "panel"
  ],
  "oldReadAhead": [
    "panel",
    "page revalidates"
  ],
  "hoverAway": [
    "panel",
    "panel"
  ],
  "superseded": {
    "reads": 4,
    "inFlight": 1,
    "afterLastPageWent": 0
  }
}
? 0
```
