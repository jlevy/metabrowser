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
The lightweight catalog continues in the background after the panel hides.
Opening the panel reads cache pages of 100 rows up to its initial display budget of 500.
Fetch more increases that budget by 500; it can prioritize the background metadata walk
when the matching rows are not cached yet.

A progress-only catalog update retains the displayed prefix and its row identity.
A changed generation stages the displayed range in bounded cache pages and accepts it
only when every page has the same source, reader, and generation.
Changing filters or hiding the panel aborts presentation reads, with late responses
unable to replace the next request’s ownership.
A failed refresh keeps cached rows and says what to do.

Holding a key changes two row marks per step and reads no detail until the walk stops.
Opening a PR can reuse the one cache-only record read made by a click, focus, or hover.
The production row mount keeps current and focused rows, text-only titles, absolute
accessibility positions, and bounded retained changed-file trees.
A variable-height spacer window bounds mounted rows as the explicit display grows.

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
        "skeleton": true,
        "listName": "Pull requests of octo/demo",
        "progress": "Catalog paused · 0 cached"
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
        "skeleton": true,
        "listName": "Pull requests of octo/demo",
        "progress": "Catalog paused · 0 cached"
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
        "skeleton": true,
        "listName": "Pull requests of octo/demo",
        "progress": "Fetching catalog… · 0 cached",
        "live": "Waiting for the list of pull requests…"
      }
    },
    {
      "step": "the top cache page arrives",
      "requests": [
        "GET /api/plugin/github/pulls?state=all&limit=100 if-none-match \"pulls-3\"",
        "GET /api/plugin/github/pulls?state=all&limit=100&after=7"
      ],
      "marks": [
        "anchor null -> 106"
      ],
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "current",
        "listName": "Pull requests of octo/demo: 102 pull requests",
        "count": "102 PRs on octo/demo",
        "window": "Showing last 100",
        "freshness": "Fetched just now by octo-reader",
        "loadMore": "ready",
        "live": "Pull requests of octo/demo: 102 pull requests",
        "rowsHeld": 100,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Merged] Say more in the guide | #8 · maintainer · topic ← guide-more | /pull/8",
          "[Open] Count to two in the app | #7 · forker · topic ← forker:count-to-two | /pull/7"
        ]
      }
    },
    {
      "step": "cached windows fill only the display budget",
      "requests": [],
      "timer": "slow",
      "painted": 1,
      "paint": {
        "filter": "all",
        "status": "current",
        "listName": "Pull requests of octo/demo: 102 pull requests",
        "count": "102 PRs on octo/demo",
        "freshness": "Fetched just now by octo-reader",
        "live": "Pull requests of octo/demo: 102 pull requests",
        "rowsHeld": 102,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Open] Work item 6 | #6 · contributor · topic ← work-6 | /pull/6",
          "[Open] Work item 5 | #5 · contributor · topic ← work-5 | /pull/5"
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
        "count": "102 PRs on octo/demo",
        "freshness": "Fetched just now by octo-reader",
        "live": "Pull requests of octo/demo: 100 pull requests",
        "rowsHeld": 100,
        "rows": [
          "[Open] Work item 106 | #106 · contributor · topic ← work-106 | /pull/106",
          "[Open] Work item 105 | #105 · contributor · topic ← work-105 | /pull/105",
          "…",
          "[Open] Work item 6 | #6 · contributor · topic ← work-6 | /pull/6",
          "[Open] Work item 5 | #5 · contributor · topic ← work-5 | /pull/5"
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
        "POST /api/plugin/github/pulls-refresh {\"state\":\"closed\",\"target\":500}"
      ],
      "timer": "slow",
      "marks": [
        "anchor null -> 6000"
      ],
      "painted": 6,
      "paint": {
        "filter": "closed",
        "status": "current",
        "listName": "Pull requests of octo/demo: 1,000 pull requests",
        "count": "1,000 PRs on octo/demo",
        "window": "Showing last 500",
        "progress": "Catalog paused · 1,000 cached",
        "freshness": "Fetched just now by octo-reader",
        "loadMore": "ready",
        "live": "Pull requests of octo/demo: 1,000 pull requests",
        "rowsHeld": 500,
        "rows": [
          "[Closed] Work item 6000 | #6000 · contributor · topic ← work-6000 | /pull/6000",
          "[Closed] Work item 5999 | #5999 · contributor · topic ← work-5999 | /pull/5999",
          "…",
          "[Closed] Work item 5502 | #5502 · contributor · topic ← work-5502 | /pull/5502",
          "[Closed] Work item 5501 | #5501 · contributor · topic ← work-5501 | /pull/5501"
        ]
      }
    },
    {
      "step": "6,000 cached: the same 500 rows stay in place",
      "requests": [
        "GET /api/plugin/github/pulls?state=closed&limit=100"
      ],
      "timer": "fast",
      "painted": 2,
      "paint": {
        "filter": "closed",
        "status": "current",
        "listName": "Pull requests of octo/demo: 6,000 pull requests",
        "count": "6,000 PRs on octo/demo",
        "window": "Showing last 500",
        "progress": "Fetching catalog… · 6,000 cached",
        "freshness": "Refreshing… · fetched just now by octo-reader",
        "loadMore": "ready",
        "live": "Pull requests of octo/demo: 6,000 pull requests",
        "rowsHeld": 500,
        "rows": [
          "[Closed] Work item 6000 | #6000 · contributor · topic ← work-6000 | /pull/6000",
          "[Closed] Work item 5999 | #5999 · contributor · topic ← work-5999 | /pull/5999",
          "…",
          "[Closed] Work item 5502 | #5502 · contributor · topic ← work-5502 | /pull/5502",
          "[Closed] Work item 5501 | #5501 · contributor · topic ← work-5501 | /pull/5501"
        ]
      }
    },
    {
      "step": "Fetch more displays another 500 cached rows without provider work",
      "requests": [
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5501",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5401",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5301",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5201",
        "GET /api/plugin/github/pulls?state=closed&limit=100&after=5101"
      ],
      "timer": "slow",
      "painted": 6,
      "paint": {
        "filter": "closed",
        "status": "current",
        "listName": "Pull requests of octo/demo: 1,000 pull requests",
        "count": "1,000 PRs on octo/demo",
        "progress": "Catalog paused · 1,000 cached",
        "freshness": "Fetched just now by octo-reader",
        "live": "Pull requests of octo/demo: 1,000 pull requests",
        "rowsHeld": 1000,
        "rows": [
          "[Closed] Work item 6000 | #6000 · contributor · topic ← work-6000 | /pull/6000",
          "[Closed] Work item 5999 | #5999 · contributor · topic ← work-5999 | /pull/5999",
          "…",
          "[Closed] Work item 5002 | #5002 · contributor · topic ← work-5002 | /pull/5002",
          "[Closed] Work item 5001 | #5001 · contributor · topic ← work-5001 | /pull/5001"
        ]
      }
    },
    {
      "step": "a new PR revalidates the display through ten bounded cache pages",
      "requests": [
        "GET /api/plugin/github/pulls?state=closed&limit=100 if-none-match \"pulls-32\"",
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
        "count": "6,001 PRs on octo/demo",
        "window": "Showing last 1,000",
        "progress": "Fetching catalog… · 6,001 cached",
        "freshness": "Refreshing… · fetched just now by octo-reader",
        "loadMore": "ready",
        "live": "Pull requests of octo/demo: 6,001 pull requests",
        "rowsHeld": 1000,
        "rows": [
          "[Closed] Work item 6001 | #6001 · contributor · topic ← work-6001 | /pull/6001",
          "[Closed] Work item 6000 | #6000 · contributor · topic ← work-6000 | /pull/6000",
          "…",
          "[Closed] Work item 5003 | #5003 · contributor · topic ← work-5003 | /pull/5003",
          "[Closed] Work item 5002 | #5002 · contributor · topic ← work-5002 | /pull/5002"
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
        "GET /api/plugin/github/pull?number=105"
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
      "requests": [],
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
        "GET /api/plugin/github/pull?number=80"
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
        "empty": "This checkout's origin is not a GitHub repository Metabrowser can list.",
        "live": "This checkout's origin is not a GitHub repository Metabrowser can list."
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
`failures` pins the typed refresh outcomes, and `landing` records the repository message
without confusing an empty filter with a repository that has no PRs.
`reader` follows a selected PR through its cache-only read and explicit detail fetch.
`paint` checks tree roles, absolute positions, numeric-only emphasis, text-only titles,
cached append behavior, and changed-file tree retention.

```console
$ node tests/dom/github-pulls-panel-second-session.js
{
  "provider_calls": {
    "source acquisition": [
      "gh api repos/octo/demo --jq .size"
    ],
    "cold cache reads": [],
    "catalog backfill": [
      "gh auth status",
      "gh api graphql catalog state=all cursor=start",
      "gh api graphql catalog state=all cursor=all-100"
    ],
    "cached windows, filters, Fetch more and reopen": [],
    "due metadata refresh": [
      "gh auth status",
      "gh api graphql catalog state=updated cursor=start"
    ],
    "fresh cached revisit": []
  },
  "failures": {
    "not_logged_in": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "GitHub CLI is not signed in to github.com. Run gh auth login --hostname github.com, then retry. You can still browse local files and any cached pull requests.",
        "retry": true
      }
    },
    "gh_too_old": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "This GitHub CLI cannot report the active account. Update gh from https://cli.github.com/, then run gh auth status --hostname github.com. You can still browse local files and any cached pull requests.",
        "retry": true,
        "help": "update"
      }
    },
    "not_found_or_private": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "The repository was not found, or the signed-in account cannot read its pull requests.",
        "retry": true
      }
    },
    "network_error": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "Offline, or GitHub could not be reached. The list is as it was last fetched.",
        "retry": true
      }
    },
    "gh_failed": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "The saved catalog refresh failed.",
        "retry": true
      }
    },
    "account_changed": {
      "status": "stale",
      "freshness": "Fetched just now by octo-reader · may be out of date",
      "notice": {
        "severity": "warning",
        "text": "The saved catalog refresh failed.",
        "retry": true
      }
    },
    "gh_missing": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com. You can still browse local files and any cached pull requests.",
        "retry": true,
        "help": "install"
      }
    },
    "cache_unwritable": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "The saved catalog refresh failed.",
        "retry": true
      }
    },
    "rate_limited": {
      "status": "current",
      "freshness": "Fetched just now by octo-reader",
      "notice": {
        "severity": "warning",
        "text": "GitHub's rate limit lifts at 2026-09-18T00:00:00.000Z. No automatic attempt runs before then.",
        "retry": false
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
    "baseRef": "main",
    "headRef": "<b>topic</b>",
    "headLabel": "<b>topic</b> (deleted fork)",
    "updatedAt": "2026-09-17T12:00:00Z",
    "refs": "main ← <b>topic</b> (deleted fork)",
    "meta": "#7 · ghost · main ← <b>topic</b> (deleted fork)"
  },
  "spelled": "main ← topic",
  "landing": {
    "a server with no repository": "This server serves no GitHub repository.",
    "a checkout whose origin cannot be listed": "This checkout's origin is not a GitHub repository Metabrowser can list.",
    "a mirror": "Select a pull request.",
    "a list with no rows, and no gh": "Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com. You can still browse local files and any cached pull requests.",
    "a polling checkout landing preserves its origin refusal": {
      "said": [
        "This checkout's origin is not a GitHub repository Metabrowser can list."
      ],
      "requests": [
        "GET /api/plugin/github/pulls?limit=0"
      ],
      "timers": []
    }
  },
  "the list's address, on a first visit": [
    {
      "step": "it mounts and reads the list",
      "requests": [
        "GET /api/plugin/github/pulls?limit=0"
      ],
      "said": [],
      "timers": []
    },
    {
      "step": "nothing cached, and the refresh not yet asked: it reads again soon",
      "requests": [],
      "said": [
        "Select a pull request."
      ],
      "timers": [
        1000
      ]
    },
    {
      "step": "the refresh is running: again at the fast poll",
      "requests": [
        "GET /api/plugin/github/pulls?limit=0"
      ],
      "said": [
        "Select a pull request."
      ],
      "timers": [
        1000
      ]
    },
    {
      "step": "the refresh failed: it says why, and reads no more",
      "requests": [
        "GET /api/plugin/github/pulls?limit=0"
      ],
      "said": [
        "Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com. You can still browse local files and any cached pull requests."
      ],
      "timers": []
    }
  ],
  "the list's address recovers": [
    {
      "step": "connection",
      "before": {
        "said": [
          "Could not read pull requests. Trying again."
        ],
        "timers": [
          30000
        ]
      },
      "after": {
        "said": [
          "Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com. You can still browse local files and any cached pull requests."
        ],
        "timers": []
      },
      "requests": [
        "GET /api/plugin/github/pulls?limit=0",
        "GET /api/plugin/github/pulls?limit=0"
      ]
    },
    {
      "step": "non-envelope",
      "before": {
        "said": [
          "Could not read pull requests. Trying again."
        ],
        "timers": [
          30000
        ]
      },
      "after": {
        "said": [
          "Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com. You can still browse local files and any cached pull requests."
        ],
        "timers": []
      },
      "requests": [
        "GET /api/plugin/github/pulls?limit=0",
        "GET /api/plugin/github/pulls?limit=0"
      ]
    },
    {
      "step": "pin changed",
      "before": {
        "said": [],
        "timers": []
      },
      "after": {
        "said": [],
        "timers": []
      },
      "requests": [
        "GET /api/plugin/github/pulls?limit=0"
      ]
    },
    {
      "step": "empty refreshing",
      "before": {
        "said": [
          "No pull requests."
        ],
        "timers": [
          1000
        ]
      },
      "after": {
        "said": [
          "Select a pull request."
        ],
        "timers": []
      },
      "requests": [
        "GET /api/plugin/github/pulls?limit=0",
        "GET /api/plugin/github/pulls?limit=0"
      ]
    }
  ],
  "reader": [
    {
      "name": "an address alone fetches nothing",
      "asked": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "waits": [
        30000
      ],
      "before": {
        "message": "This pull request has not been fetched yet.",
        "canRefresh": true
      },
      "after": {
        "message": "This pull request has not been fetched yet.",
        "canRefresh": true
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
        "canRefresh": false
      },
      "after": {
        "message": "Fetching the pull request…",
        "canRefresh": false
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
        "canRefresh": false
      },
      "after": {
        "message": "Fetching the pull request…",
        "canRefresh": false
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
        "canRefresh": false
      },
      "after": {
        "message": "Fetching the pull request…",
        "canRefresh": false
      },
      "once let go": {
        "asked": [
          "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"wait_core\":true}"
        ],
        "message": "Fetching the pull request…"
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
        "canRefresh": false
      },
      "after": {
        "message": "The refresh was refused (too many pull requests are being fetched; try again when one has finished).",
        "canRefresh": true
      }
    },
    {
      "name": "a row with a record fetches nothing",
      "asked": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "waits": [
        30000
      ],
      "before": {
        "message": null,
        "canRefresh": false
      },
      "after": {
        "message": null,
        "canRefresh": false
      }
    }
  ],
  "paint": {
    "only the exact number is bold": [
      {
        "node": "STRONG",
        "text": "102"
      },
      {
        "node": "#text",
        "text": " PRs on octo/demo"
      }
    ],
    "the list": "ul .github-pulls-list role=\"tree\" aria-label=\"Pull requests of octo/demo: 102 pull requests\"",
    "a row": [
      "li .github-pulls-item role=\"none\"",
      "a .github-pulls-row.collapsed href=\"/pull/106\" role=\"treeitem\" aria-level=\"1\" aria-expanded=\"false\" tabindex=\"-1\" aria-posinset=\"1\" aria-setsize=\"102\""
    ],
    "the row whose page is shown": "a .github-pulls-row.selected.expanded href=\"/pull/105\" role=\"treeitem\" aria-level=\"1\" aria-expanded=\"true\" tabindex=\"0\" aria-current=\"page\" aria-selected=\"true\" aria-owns=\"github-pull-files-105\" aria-posinset=\"2\" aria-setsize=\"102\"",
    "its parts": [
      "span .github-pulls-toggle aria-hidden=\"true\"",
      "span .github-pull-state-icon role=\"img\" aria-label=\"Open\"",
      "span .github-pulls-title",
      "span .github-pulls-age.age-hour",
      "span .github-pulls-meta"
    ],
    "its changed files, read from the cache": "/api/plugin/github/pull-files?number=105&offset=0",
    "they hang under it as a group it owns": [
      "a .github-pulls-row.selected.expanded href=\"/pull/105\" role=\"treeitem\" aria-level=\"1\" aria-expanded=\"true\" tabindex=\"0\" aria-current=\"page\" aria-selected=\"true\" aria-owns=\"github-pull-files-105\" aria-posinset=\"2\" aria-setsize=\"102\"",
      "div .tree-children.github-pull-files role=\"group\" id=\"github-pull-files-105\" aria-label=\"Changed files of #105: 2 files\""
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
    "closing twelve expanded trees enforces retention immediately": {
      "whileExpanded": 10,
      "afterClosingAll": 9
    },
    "disposed: what is left in the tab": 0
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
{"authoritativeMembership":true,"multipleStacks":true,"identityGuard":true,"tabAndReaderIntent":true,"sharedRead":true,"failureRetention":true,"retryWindow":true,"disposal":true,"lateOwnerGuard":true,"initialFailureRetry":true}
? 0
```

The mounted PR page uses a shared gray skeleton only while cold or pending.
Cached refreshes stay readable.
Native stack members are created on disclosure; Previous PR and Next PR preserve the
active tab, clear file selection, and carry a reader’s explicit fetch intent.
An identity-only response removes the old source’s enrichment.

```console
$ node tests/dom/github-pull-stack-mount-behavior.js
{"coldSkeleton":true,"pendingSkeleton":true,"cachedRefreshRetained":true,"authoritativeStack":true,"orderedNeighbors":true,"tabPreserved":true,"fileCleared":true,"explicitReaderIntent":true,"disposedWorkReleased":true}
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

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
