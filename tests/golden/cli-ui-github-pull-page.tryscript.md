---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Pull-Request Page

A pull request’s page at `/pull/<n>` renders the cached record the GitHub plugin’s pull
route answers: header, state, merge status, labels, the conversation with review states,
review comments with their file, line, and diff hunk, checks, and notes.
It polls that route while the page is visible, quickly while a refresh runs or the
record is pending and slowly otherwise, with `If-None-Match` so an unchanged answer is a
304 and repaints nothing.
A visible page with nothing cached fetches its record through
`POST /api/plugin/github/pull-refresh`. A page with an earlier failure leaves Fetch
available, and a refused press says why.
A stale page refreshes itself, without `retry`, and offers nothing to press while it
does: once a reader has stayed on it, so a page walked past asks nothing, and again each
time it goes stale while it is left open, at once (`leftOpen`). A page whose own refresh
is not due or failed asks again only once a freshness window has passed, and keeps
saying why meanwhile (`failing`). GitHub’s rate limit is a hold, not a failure
(`rateLimited`): the page offers no Refresh, names the time it asks again, not before
`reset_at` and not within a window of the refused attempt, wakes then, and asks at once.
`revalidating` says the content shown is being refreshed, which the paint shows by
breathing the age line, never with a spinner, and the freshness is the plain age, never
“may be out of date”.
The Markdown of each text is asked for one part at a time from
`/api/plugin/github/pull-markdown`, two at once, and a render of a record the page no
longer shows is dropped.
`browse` is what Browse code does: a link when the head is served, and otherwise, with
nothing to warn about, it serves the head and then opens the root.
Only a page served an older head of this pull request gets `headOffer`, the offer of the
newer one.

This browserless session loads the production `builtin_plugins/github/pull-page.js` and
plays the server’s side from `tests/fixtures/github-pull-page-responses.json`: what the
in-process application answered while it served pull request 7 of the stand-in in
`tests/github_pull_fixture.py`, from nothing cached, through a fetch, to a stale record
and a refresh that brought one more comment, and what it answered of other numbers.
`tests/test_github_pull_page_session.py` replays that story and fails when the recording
drifts. Timers, the clock, visibility, and paint are injected; the browser’s visibility
observer is played by asking for parts in reading order.
`states` is the header, in github.com’s verbs with the branches as head → base, and the
checks as GitHub counts them for the open pull request and for the stand-in’s merged and
closed ones, which the same server answered: “wants to merge” with the commit count
until it is merged, then the account that merged it, or no one when the record names no
merger, and skipped checks apart from neutral ones.
Pull requests 7 and 9 come from forks, so both sides carry their owner, as github.com’s
header does; pull request 8 is from the same repository, so both sides are bare branch
names. The last lines show which links a rendered text keeps (made absolute against the
pull request’s github.com page, http and https only), and the `/view/` address a review
comment’s file opens at.
`checkActions` is where each check’s link opens, for the recorded checks and six the
session adds: a GitHub Actions run says **View action on GitHub**, another page on a
host the shell marks as GitHub’s, here a gist, **View on GitHub**, and a check’s own
site **View details**, as does a github.com address with a port or credentials, which
the shell does not mark; each link’s accessible name adds its check’s name; an address a
page may not follow, here `ftp:`, has no link; and a run’s app is its description unless
an Actions link already says so.
Each check line of a paint gives its status, name, description, and link the same way.
`hunks` is what a review comment shows of its diff hunk, which ends at the commented
line: the last eight lines, or back to the start of a multi-line comment’s range, with
the rest behind a disclosure, and each line classed so an addition or deletion is
tinted. The stand-in’s hunks are short, so the session writes the long ones.
A page asked for a tab it does not have, which the route’s grammar never sends, stays on
one it has. `place` is a reader’s place in the pane through history, kept in the history
entry as a block and how far into it, on a stage that stands for the pane.
A new entry starts at the top.
Back onto an entry waits for its page and puts the pane at that block, and back again
each time the page changes height, until the reader moves it or the page has been still.
A reader who moved first keeps the pane where they took it, and an address with a
fragment is left alone.
It asserts, and so prints nothing for, that no pace of moves writes a place more often
than Safari’s limit on `history.replaceState`, and that only a key that can move the
pane ends a hold.

```console
$ node tests/dom/github-pull-page-session.js
{
  "steps": [
    {
      "step": "open with nothing cached",
      "requests": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "timer": "slow",
      "paints": 2,
      "paint": {
        "status": "pending",
        "tab": "conversation",
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "freshness": null,
        "failure": null,
        "header": null,
        "labels": [],
        "merge": null,
        "timeline": [],
        "reviewComments": [],
        "checks": null,
        "notes": [],
        "browse": null,
        "headOffer": null,
        "comparison": null
      },
      "markdown": []
    },
    {
      "step": "a visible cold page fetches itself",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"wait_core\":true}"
      ],
      "timer": "fast",
      "paints": 1,
      "paint": {
        "status": "pending",
        "tab": "conversation",
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "freshness": null,
        "failure": null,
        "header": null,
        "labels": [],
        "merge": null,
        "timeline": [],
        "reviewComments": [],
        "checks": null,
        "notes": [],
        "browse": null,
        "headOffer": null,
        "comparison": null
      },
      "markdown": []
    },
    {
      "step": "still fetching",
      "requests": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "timer": "fast",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "the record arrives",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer [reviewed] 2026-09-16T12:32:50Z review/3274109685",
          "comment maintainer 2026-09-16T17:34:17Z issue_comment/3341937855",
          "review maintainer [approved] 2026-09-16T17:36:02Z review/3279967139"
        ],
        "reviewComments": [
          "src/app.txt:outdated maintainer +hunk",
          "src/app.txt:2 forker (reply) +hunk"
        ],
        "checks": {
          "counts": {
            "success": 2,
            "pending": 1
          },
          "items": [
            "[success] tests (3.13) -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "browse": "switches to refs/pull/7/head",
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "repaint",
      "markdown": []
    },
    {
      "step": "an unchanged answer is a 304",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "a reader reaches four texts; two renders run at once",
      "requests": [
        "GET /api/plugin/github/pull-markdown?number=7&part=body",
        "GET /api/plugin/github/pull-markdown?number=7&part=issue_comment%2F3341937855"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": [],
      "waiting": {
        "inFlight": 2,
        "queued": [
          "review/3279967139",
          "review_comment/2383608906"
        ]
      }
    },
    {
      "step": "the renders arrive",
      "requests": [
        "GET /api/plugin/github/pull-markdown?number=7&part=review%2F3279967139",
        "GET /api/plugin/github/pull-markdown?number=7&part=review_comment%2F2383608906"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": [
        "body: <div><div><p>The app counts to one.</p>\n<p>This teaches it <strong>two</strong>.</p></div></div>",
        "issue_comment/3341937855: <div><div><p>Thanks. CI is green; one question inline.</p></div></div>",
        "review/3279967139: <div><div><p>Looks right.</p></div></div>",
        "review_comment/2383608906: <div><div><p>Why does this line change?</p></div></div>"
      ]
    },
    {
      "step": "a part asked for again comes from memory",
      "requests": [],
      "timer": "slow",
      "paints": 0,
      "markdown": [
        "body: <div><div><p>The app counts to one.</p>\n<p>This teaches it <strong>two</strong>.</p></div></div>"
      ]
    },
    {
      "step": "a part the record lacks stays plain",
      "requests": [
        "GET /api/plugin/github/pull-markdown?number=7&part=issue_comment%2F1"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "Browse code that the server refuses says why and stays",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/pull/7/head\"}"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": "Could not switch to the head (selection_not_found).",
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer [reviewed] 2026-09-16T12:32:50Z review/3274109685",
          "comment maintainer 2026-09-16T17:34:17Z issue_comment/3341937855",
          "review maintainer [approved] 2026-09-16T17:36:02Z review/3279967139"
        ],
        "reviewComments": [
          "src/app.txt:outdated maintainer +hunk",
          "src/app.txt:2 forker (reply) +hunk"
        ],
        "checks": {
          "counts": {
            "success": 2,
            "pending": 1
          },
          "items": [
            "[success] tests (3.13) -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "browse": "switches to refs/pull/7/head",
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "Browse code serves the head and opens the root",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/pull/7/head\"}"
      ],
      "timer": "slow",
      "paints": 0,
      "navigated": [
        "/view/"
      ],
      "markdown": []
    },
    {
      "step": "on the head, Browse code is a link",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer [reviewed] 2026-09-16T12:32:50Z review/3274109685",
          "comment maintainer 2026-09-16T17:34:17Z issue_comment/3341937855",
          "review maintainer [approved] 2026-09-16T17:36:02Z review/3279967139"
        ],
        "reviewComments": [
          "src/app.txt:outdated maintainer +hunk",
          "src/app.txt:2 forker (reply) +hunk"
        ],
        "checks": {
          "counts": {
            "success": 2,
            "pending": 1
          },
          "items": [
            "[success] tests (3.13) -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "browse": "link to the root",
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "repaint",
      "markdown": []
    },
    {
      "step": "with a link, the controller switches nothing",
      "requests": [],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "open Changes",
      "requests": [],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "current",
        "tab": "files",
        "message": null,
        "canRefresh": true,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer [reviewed] 2026-09-16T12:32:50Z review/3274109685",
          "comment maintainer 2026-09-16T17:34:17Z issue_comment/3341937855",
          "review maintainer [approved] 2026-09-16T17:36:02Z review/3279967139"
        ],
        "reviewComments": [
          "src/app.txt:outdated maintainer +hunk",
          "src/app.txt:2 forker (reply) +hunk"
        ],
        "checks": {
          "counts": {
            "success": 2,
            "pending": 1
          },
          "items": [
            "[success] tests (3.13) -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "browse": "link to the root",
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "markdown": []
    },
    {
      "step": "back to the conversation",
      "requests": [],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer [reviewed] 2026-09-16T12:32:50Z review/3274109685",
          "comment maintainer 2026-09-16T17:34:17Z issue_comment/3341937855",
          "review maintainer [approved] 2026-09-16T17:36:02Z review/3279967139"
        ],
        "reviewComments": [
          "src/app.txt:outdated maintainer +hunk",
          "src/app.txt:2 forker (reply) +hunk"
        ],
        "checks": {
          "counts": {
            "success": 2,
            "pending": 1
          },
          "items": [
            "[success] tests (3.13) -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "browse": "link to the root",
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "the record goes stale",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 1,
      "askWaits": true,
      "paint": {
        "status": "stale",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 5 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer [reviewed] 2026-09-16T12:32:50Z review/3274109685",
          "comment maintainer 2026-09-16T17:34:17Z issue_comment/3341937855",
          "review maintainer [approved] 2026-09-16T17:36:02Z review/3279967139"
        ],
        "reviewComments": [
          "src/app.txt:outdated maintainer +hunk",
          "src/app.txt:2 forker (reply) +hunk"
        ],
        "checks": {
          "counts": {
            "success": 2,
            "pending": 1
          },
          "items": [
            "[success] tests (3.13) -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "browse": "link to the root",
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "the reader stayed: the page asks for a refresh by itself",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7}"
      ],
      "timer": "fast",
      "paints": 1,
      "paint": {
        "status": "stale",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 5 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer [reviewed] 2026-09-16T12:32:50Z review/3274109685",
          "comment maintainer 2026-09-16T17:34:17Z issue_comment/3341937855",
          "review maintainer [approved] 2026-09-16T17:36:02Z review/3279967139"
        ],
        "reviewComments": [
          "src/app.txt:outdated maintainer +hunk",
          "src/app.txt:2 forker (reply) +hunk"
        ],
        "checks": {
          "counts": {
            "success": 2,
            "pending": 1
          },
          "items": [
            "[success] tests (3.13) -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "browse": "link to the root",
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "still refreshing",
      "requests": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "timer": "fast",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "a refresh that changed no text keeps the conversation",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer [reviewed] 2026-09-16T12:32:50Z review/3274109685",
          "comment maintainer 2026-09-16T17:34:17Z issue_comment/3341937855",
          "review maintainer [approved] 2026-09-16T17:36:02Z review/3279967139"
        ],
        "reviewComments": [
          "src/app.txt:outdated maintainer +hunk",
          "src/app.txt:2 forker (reply) +hunk"
        ],
        "checks": {
          "counts": {
            "success": 2,
            "pending": 1
          },
          "items": [
            "[success] tests (3.13) -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "browse": "link to the root",
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "a same-content render remains usable after a refresh",
      "requests": [],
      "timer": "slow",
      "paints": 0,
      "markdown": [
        "body: <div><div><p>The app counts to one.</p>\n<p>This teaches it <strong>two</strong>.</p></div></div>"
      ]
    },
    {
      "step": "another refresh brought a comment full of markup",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer [reviewed] 2026-09-16T12:32:50Z review/3274109685",
          "comment maintainer 2026-09-16T17:34:17Z issue_comment/3341937855",
          "review maintainer [approved] 2026-09-16T17:36:02Z review/3279967139",
          "comment forker 2026-09-17T12:03:00Z issue_comment/3341937856"
        ],
        "reviewComments": [
          "src/app.txt:outdated maintainer +hunk",
          "src/app.txt:2 forker (reply) +hunk"
        ],
        "checks": {
          "counts": {
            "success": 2,
            "pending": 1
          },
          "items": [
            "[success] tests (3.13) -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> View action on GitHub https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo (Read the Docs build succeeded!) -> View details https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "browse": "link to the root",
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "repaint",
      "markdown": []
    },
    {
      "step": "the hook sends the comment inert",
      "requests": [
        "GET /api/plugin/github/pull-markdown?number=7&part=issue_comment%2F3341937856"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": [
        "issue_comment/3341937856: <div><div><p>Rebased on <code>topic</code>; see <a href=\"https://github.com/octo/demo/pull/docs/new.md\" target=\"_blank\" rel=\"noopener noreferrer\">the docs</a>.</p>\n\n<a href=\"https://example.com/badge.png\" target=\"_blank\" rel=\"noopener noreferrer\">build badge</a> <span>image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>\n</div></div>"
      ]
    },
    {
      "step": "a hidden page stops polling",
      "requests": [],
      "timer": null,
      "paints": 0,
      "markdown": []
    },
    {
      "step": "shown again, it polls at once",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "dispose",
      "requests": [],
      "timer": null,
      "paints": 0,
      "markdown": []
    },
    {
      "step": "a page opened in the background reads once and asks for nothing",
      "requests": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "timer": null,
      "paints": 2,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": true,
        "freshness": "Fetched 5 min ago via GitHub CLI",
        "failure": null,
        "browse": "link to the root",
        "headOffer": null
      },
      "markdown": []
    },
    {
      "step": "shown, its ask waits for the reader to stay",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 1,
      "askWaits": true,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 5 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "browse": "link to the root",
        "headOffer": null
      },
      "markdown": []
    },
    {
      "step": "the reader stayed: it asks",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7}"
      ],
      "timer": "fast",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 5 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "browse": "link to the root",
        "headOffer": null
      },
      "markdown": []
    },
    {
      "step": "a page walked past reads once",
      "requests": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "timer": "slow",
      "paints": 2,
      "askWaits": true,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 5 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "browse": "link to the root",
        "headOffer": null
      },
      "conversation": "repaint",
      "markdown": []
    },
    {
      "step": "and leaves before its ask, which is cancelled",
      "requests": [],
      "timer": null,
      "paints": 0,
      "markdown": []
    },
    {
      "step": "served an older head, the page offers the newer one",
      "requests": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "timer": "slow",
      "paints": 2,
      "paint": {
        "status": "current",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "browse": "link to the root",
        "headOffer": "refs/pull/7/head"
      },
      "conversation": "repaint",
      "markdown": []
    },
    {
      "step": "taking the offer reloads",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/pull/7/head\"}"
      ],
      "timer": "slow",
      "paints": 0,
      "reloads": 1,
      "markdown": []
    },
    {
      "step": "a cold page with an earlier failure leaves Fetch available",
      "requests": [
        "GET /api/plugin/github/pull?number=14"
      ],
      "timer": "slow",
      "paints": 2,
      "paint": {
        "status": "absent",
        "message": "This pull request has not been fetched yet.",
        "canRefresh": true,
        "freshness": null,
        "failure": "The last refresh failed: gh could not reach api.github.com",
        "browse": null,
        "headOffer": null
      },
      "markdown": []
    },
    {
      "step": "polling it asks for no fetch",
      "requests": [
        "GET /api/plugin/github/pull?number=14 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "nor does showing it again",
      "requests": [
        "GET /api/plugin/github/pull?number=14 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "a press past the bound is refused and says why",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":14,\"retry\":true,\"wait_core\":true}"
      ],
      "timer": "slow",
      "paints": 2,
      "paint": {
        "status": "absent",
        "message": "The refresh was refused (too many pull requests are being fetched; try again when one has finished).",
        "canRefresh": true,
        "freshness": null,
        "failure": "The last refresh failed: gh could not reach api.github.com",
        "browse": null,
        "headOffer": null
      },
      "markdown": []
    },
    {
      "step": "a page opened on a tab it does not have shows the conversation",
      "requests": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "timer": "slow",
      "paints": 2,
      "paint": {
        "status": "pending",
        "tab": "conversation",
        "message": "Fetching the pull request…",
        "canRefresh": false,
        "freshness": null,
        "failure": null,
        "header": null,
        "labels": [],
        "merge": null,
        "timeline": [],
        "reviewComments": [],
        "checks": null,
        "notes": [],
        "browse": null,
        "headOffer": null,
        "comparison": null
      },
      "markdown": []
    },
    {
      "step": "a tab it does not have is not taken later",
      "requests": [],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    }
  ],
  "states": {
    "open": {
      "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
      "checks": {
        "success": 2,
        "pending": 1
      }
    },
    "merged": {
      "header": "Say more in the guide #8 [Merged] octo merged 1 commit: guide-more → topic",
      "checks": {
        "success": 2,
        "skipped": 1
      }
    },
    "closed": {
      "header": "spam #9 [Closed] ghost wants to merge 1 commit: spam (deleted fork) → octo:topic",
      "checks": {
        "success": 2,
        "pending": 1
      }
    },
    "merged_unattributed": {
      "header": "Say more in the guide #8 [Merged] merged 1 commit: guide-more → topic",
      "checks": {
        "success": 2,
        "skipped": 1
      }
    }
  },
  "notGithub": {
    "status": "absent",
    "message": "This server serves no GitHub repository.",
    "canRefresh": false
  },
  "links": [
    {
      "href": "docs/new.md",
      "followed": "https://github.com/octo/demo/pull/docs/new.md"
    },
    {
      "href": "https://example.com/a",
      "followed": "https://example.com/a"
    },
    {
      "href": "javascript:alert(1)",
      "followed": null
    },
    {
      "href": "data:text/html,x",
      "followed": null
    },
    {
      "href": "//evil.example/x",
      "followed": "https://evil.example/x"
    }
  ],
  "wire": "g1-c3Jj/g1-YXBwLnR4dA",
  "pageDefense": "<p>Rebased on <code>topic</code>; see <a href=\"https://github.com/octo/demo/pull/docs/new.md\" target=\"_blank\" rel=\"noopener noreferrer\">the docs</a>.</p>\n\n<a href=\"https://example.com/badge.png\" target=\"_blank\" rel=\"noopener noreferrer\">build badge</a> <span>image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>\n",
  "filesChanged": [
    "nothing open yet: mount",
    "open on the record's comparison: keep",
    "open on an older head: offer",
    "no comparison in the record: unavailable"
  ]
}
? 0
```

The session is printed in two parts, by `github-pull-page-session.js` and by
`github-pull-page-second-session.js`, which runs the same session whole, because
tryscript matches a command’s expected output as one regular expression, and the
transcript in one block is larger than V8 compiles.
The second part is what the Changes tab says when the comparison is unavailable, a
server with no store among them, the page on a checkout, the review comments’ hunks, and
the reader’s place.
A checkout’s page has no pin, so no Browse code and no switch, and it
says only when the checkout’s is the pull request’s head.

```console
$ node tests/dom/github-pull-page-second-session.js
{
  "leftOpen": [
    {
      "step": "a page left open asks for its refresh",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7}"
      ],
      "timer": "fast",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 5 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "browse": "link to the root",
        "headOffer": null
      },
      "conversation": "repaint",
      "markdown": []
    },
    {
      "step": "the refresh lands",
      "requests": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "current",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "browse": "link to the root",
        "headOffer": null
      },
      "conversation": "repaint",
      "markdown": []
    },
    {
      "step": "a minute on, its record goes stale again",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 1 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "browse": "link to the root",
        "headOffer": null
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "it asks for the next refresh at once",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7}"
      ],
      "timer": "fast",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 1 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "browse": "link to the root",
        "headOffer": null
      },
      "conversation": "keep",
      "markdown": []
    }
  ],
  "failing": [
    {
      "step": "a stale page asks once, and its refresh is not due",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":8}"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": true,
        "freshness": "Fetched 24 min ago via GitHub CLI",
        "failure": "The last refresh failed: gh could not reach api.github.com",
        "browse": "switches to refs/pull/8/head",
        "headOffer": null
      },
      "conversation": "repaint",
      "markdown": []
    },
    {
      "step": "its next poll asks nothing",
      "requests": [
        "GET /api/plugin/github/pull?number=8 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "shown again within the window, it asks nothing",
      "requests": [
        "GET /api/plugin/github/pull?number=8 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "a window later and still stale, its poll asks again at once",
      "requests": [
        "GET /api/plugin/github/pull?number=8 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 25 min ago via GitHub CLI",
        "revalidating": true,
        "failure": "The last refresh failed: gh could not reach api.github.com",
        "browse": "switches to refs/pull/8/head",
        "headOffer": null
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "that ask is sent with no wait, and is not due",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":8}"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": true,
        "freshness": "Fetched 25 min ago via GitHub CLI",
        "failure": "The last refresh failed: gh could not reach api.github.com",
        "browse": "switches to refs/pull/8/head",
        "headOffer": null
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "a reader's Refresh is always taken",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":8,\"retry\":true}"
      ],
      "timer": "fast",
      "paints": 2,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 25 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "browse": "switches to refs/pull/8/head",
        "headOffer": null
      },
      "conversation": "keep",
      "markdown": []
    }
  ],
  "rateLimited": [
    {
      "step": "a stale page asks for its refresh",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7}"
      ],
      "timer": "fast",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 5 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "browse": "link to the root",
        "headOffer": null
      },
      "conversation": "repaint",
      "markdown": []
    },
    {
      "step": "GitHub's rate limit refused it",
      "requests": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 5 min ago via GitHub CLI",
        "failure": "GitHub rate limit · next check at 2026-09-17T12:06:32Z",
        "browse": "link to the root",
        "headOffer": null
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "still held, it wakes at the time it named",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": 20000,
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 6 min ago via GitHub CLI",
        "failure": "GitHub rate limit · next check at 2026-09-17T12:06:32Z",
        "browse": "link to the root",
        "headOffer": null
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "at the time it named, its poll asks again at once",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 6 min ago via GitHub CLI",
        "revalidating": true,
        "failure": "GitHub rate limit · next check at 2026-09-17T12:06:32Z",
        "browse": "link to the root",
        "headOffer": null
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "and sends that ask with no wait",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7}"
      ],
      "timer": "fast",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 6 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "browse": "link to the root",
        "headOffer": null
      },
      "conversation": "keep",
      "markdown": []
    }
  ],
  "checkActions": [
    {
      "name": "tests (3.13)",
      "detail": null,
      "action": {
        "kind": "actions",
        "href": "https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
        "label": "View action on GitHub",
        "name": "View action on GitHub: tests (3.13)"
      }
    },
    {
      "name": "docs",
      "detail": null,
      "action": {
        "kind": "actions",
        "href": "https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
        "label": "View action on GitHub",
        "name": "View action on GitHub: docs"
      }
    },
    {
      "name": "coverage",
      "detail": "Codecov",
      "action": {
        "kind": "github",
        "href": "https://github.com/octo/demo/runs/123",
        "label": "View on GitHub",
        "name": "View on GitHub: coverage"
      }
    },
    {
      "name": "lint",
      "detail": "GitHub Actions",
      "action": {
        "kind": "external",
        "href": "https://ci.example/runs/2",
        "label": "View details",
        "name": "View details: lint"
      }
    },
    {
      "name": "gist",
      "detail": "Gist bot",
      "action": {
        "kind": "github",
        "href": "https://gist.github.com/octo/abc",
        "label": "View on GitHub",
        "name": "View on GitHub: gist"
      }
    },
    {
      "name": "proxied",
      "detail": "Proxy",
      "action": {
        "kind": "external",
        "href": "https://github.com:8443/octo/demo/actions/runs/9",
        "label": "View details",
        "name": "View details: proxied"
      }
    },
    {
      "name": "credentialed",
      "detail": "Bot",
      "action": {
        "kind": "external",
        "href": "https://bot@github.com/octo/demo/runs/5",
        "label": "View details",
        "name": "View details: credentialed"
      }
    },
    {
      "name": "docs/readthedocs.org:demo",
      "detail": "Read the Docs build succeeded!",
      "action": {
        "kind": "external",
        "href": "https://demo--7.org.readthedocs.build/en/7/",
        "label": "View details",
        "name": "View details: docs/readthedocs.org:demo"
      }
    },
    {
      "name": "legacy-ci",
      "detail": "Passed",
      "action": null
    }
  ],
  "filesUnavailable": {
    "fetch_failed": {
      "files": "Changes are unavailable: the pull request's base could not be compared with its head.",
      "notes": [
        "Changes could not be read (fetch failed)."
      ]
    },
    "no_merge_base": {
      "files": "Changes are unavailable: the pull request's base could not be compared with its head.",
      "notes": [
        "Changes could not be read (no merge base)."
      ]
    },
    "base_uncertain": {
      "files": "Changes are not shown: this checkout's history is too shallow to know what this pull request changed. Metabrowser does not guess. A refresh with the network available fetches more history.",
      "notes": [
        "Changes could not be read (base uncertain)."
      ]
    },
    "commits_unavailable": {
      "files": "Changes are unavailable: a commit of this pull request's history is not readable here. On a mirror borrowing from a checkout, the checkout no longer holds it.",
      "notes": [
        "Changes could not be read (commits unavailable)."
      ]
    },
    "no_store": {
      "files": "Changes could not be fetched.",
      "notes": []
    },
    "comparison_timeout": {
      "files": "Changes are unavailable: checking this pull request's history took too long. Refresh to try again.",
      "notes": [
        "Changes could not be read (comparison timeout)."
      ]
    },
    "comparison_too_large": {
      "files": "Changes are unavailable: checking this pull request's history exceeded the comparison limit.",
      "notes": [
        "Changes could not be read (comparison too large)."
      ]
    }
  },
  "checkout": {
    "HEAD is the pull request's head": {
      "browse": null,
      "headOffer": null,
      "checkoutAtHead": "This checkout's HEAD is this pull request's head.",
      "comparison": null,
      "files": "Changes could not be fetched."
    },
    "HEAD is elsewhere": {
      "browse": null,
      "headOffer": null,
      "checkoutAtHead": null,
      "comparison": null,
      "files": "Changes could not be fetched."
    },
    "no repository context": {
      "browse": null,
      "headOffer": null,
      "checkoutAtHead": null,
      "comparison": null,
      "files": "Changes could not be fetched."
    },
    "a mirror's page, whatever it is handed": {
      "browse": "switches to refs/pull/7/head",
      "checkoutAtHead": null
    }
  },
  "hunks": {
    "a short hunk is whole": {
      "earlier": null,
      "shown": [
        "hunk: @@ -1 +1,2 @@",
        "context:  one",
        "add: +two"
      ]
    },
    "the header and a tail's worth is whole: a disclosure hides no single line": {
      "earlier": null,
      "shown": [
        "hunk: @@ -1,30 +1,30 @@ def main():",
        "context:  line 23",
        "context:  line 24",
        "context:  line 25",
        "context:  line 26",
        "context:  line 27",
        "context:  line 28",
        "context:  line 29",
        "context:  line 30"
      ]
    },
    "one line more is past the tail": {
      "earlier": "2 lines: hunk: @@ -1,30 +1,30 @@ def main(): ... context:  line 22",
      "shown": [
        "context:  line 23",
        "context:  line 24",
        "context:  line 25",
        "context:  line 26",
        "context:  line 27",
        "context:  line 28",
        "context:  line 29",
        "context:  line 30"
      ]
    },
    "a long hunk shows its tail": {
      "earlier": "25 lines: hunk: @@ -1,30 +1,30 @@ def main(): ... context:  line 23",
      "shown": [
        "context:  line 24",
        "del: -old 25",
        "add: +new 25",
        "context:  line 26",
        "context:  line 27",
        "context:  line 28",
        "context:  line 29",
        "context:  line 30"
      ]
    },
    "a range longer than the tail is all shown, from its first line, not counting a deletion": {
      "earlier": "14 lines: hunk: @@ -1,30 +1,30 @@ def main(): ... context:  line 13",
      "shown": [
        "context:  line 14",
        "del: -old 15",
        "add: +new 15",
        "context:  line 16",
        "context:  line 17",
        "context:  line 18",
        "context:  line 19",
        "context:  line 20",
        "context:  line 21",
        "context:  line 22",
        "context:  line 23",
        "context:  line 24",
        "del: -old 25",
        "add: +new 25",
        "context:  line 26",
        "context:  line 27",
        "context:  line 28",
        "context:  line 29",
        "context:  line 30"
      ]
    },
    "a range on the left counts deletions and not additions": {
      "earlier": "15 lines: hunk: @@ -1,30 +1,30 @@ def main(): ... context:  line 14",
      "shown": [
        "del: -old 15",
        "add: +new 15",
        "context:  line 16",
        "context:  line 17",
        "context:  line 18",
        "context:  line 19",
        "context:  line 20",
        "context:  line 21",
        "context:  line 22",
        "context:  line 23",
        "context:  line 24",
        "del: -old 25",
        "add: +new 25",
        "context:  line 26",
        "context:  line 27",
        "context:  line 28",
        "context:  line 29",
        "context:  line 30"
      ]
    },
    "an outdated comment's range is its original one": {
      "earlier": "14 lines: hunk: @@ -1,30 +1,30 @@ def main(): ... context:  line 13",
      "shown": [
        "context:  line 14",
        "del: -old 15",
        "add: +new 15",
        "context:  line 16",
        "context:  line 17",
        "context:  line 18",
        "context:  line 19",
        "context:  line 20",
        "context:  line 21",
        "context:  line 22",
        "context:  line 23",
        "context:  line 24",
        "del: -old 25",
        "add: +new 25",
        "context:  line 26",
        "context:  line 27",
        "context:  line 28",
        "context:  line 29",
        "context:  line 30"
      ]
    },
    "a range above what the record kept shows all it kept": {
      "earlier": null,
      "shown": [
        "context:  line 19",
        "context:  line 20",
        "context:  line 21",
        "context:  line 22",
        "context:  line 23",
        "context:  line 24",
        "context:  line 25",
        "context:  line 26",
        "context:  line 27",
        "context:  line 28",
        "context:  line 29",
        "context:  line 30"
      ]
    },
    "a range of the most shown is all shown": {
      "earlier": "31 lines: hunk: @@ -1,30 +1,30 @@ def main(): ... context:  line 30",
      "shown": "100 lines: context:  line 31 ... context:  line 130"
    },
    "a range past the most shown shows the most, and the rest is behind the disclosure": {
      "earlier": "31 lines: hunk: @@ -1,30 +1,30 @@ def main(): ... context:  line 30",
      "shown": "100 lines: context:  line 31 ... context:  line 130"
    },
    "the other side's lines do not carry a range past the most shown": {
      "earlier": "145 lines: hunk: @@ -1,30 +1,30 @@ def main(): ... del: -old 142",
      "shown": [
        "del: -old 143",
        "del: -old 144",
        "del: -old 145",
        "del: -old 146",
        "del: -old 147",
        "del: -old 148",
        "del: -old 149",
        "add: +new 30"
      ]
    },
    "a hunk's text is only ever text": {
      "earlier": null,
      "shown": [
        "hunk: @@ -1,30 +1,30 @@ def main():",
        "add: +<img src=x onerror=alert(1)>",
        "del: -</pre><script>alert(1)</script>",
        "context:  @@ not a header",
        "note: \\ No newline at end of file"
      ]
    }
  },
  "place": {
    "a new entry starts at the top and writes nothing": "pane at 0; entry null; 0 written; nothing running",
    "the page paints: the pane stays at the top": "pane at 0; entry null; 0 written; nothing running",
    "the reader scrolls: nothing is written while the pane moves": "pane at 900; entry null; 0 written; write waiting",
    "the pane is still: its place is written": "pane at 900; entry {\"block\":2,\"offset\":80,\"top\":900}; 1 written; nothing running",
    "still in the header: the scroll offset says where": "pane at 80; entry {\"block\":-1,\"offset\":0,\"top\":80}; 1 written; nothing running",
    "a click writes a waiting place before it can leave this entry": "pane at 900; entry {\"block\":2,\"offset\":80,\"top\":900}; 1 written; nothing running",
    "with nothing waiting, a click writes nothing": "pane at 900; entry {\"block\":2,\"offset\":80,\"top\":900}; 0 written; nothing running",
    "back: nothing is painted, so the place waits": "pane at 0; entry {\"block\":2,\"offset\":80,\"top\":900}; 0 written; holding",
    "the page paints: the pane goes to the block, not to the pixels": "pane at 700; entry {\"block\":2,\"offset\":80,\"top\":900}; 0 written; holding, settling",
    "a text at the place renders: the block's top has not moved": "pane at 700; entry {\"block\":2,\"offset\":80,\"top\":900}; 0 written; holding, settling",
    "a text above the place renders: the pane is put back": "pane at 1050; entry {\"block\":2,\"offset\":80,\"top\":900}; 0 written; holding, settling",
    "the hold's own scrolling is not the reader's and writes nothing": "pane at 1050; entry {\"block\":2,\"offset\":80,\"top\":900}; 0 written; holding, settling",
    "the page has been still long enough: the landing is over": "pane at 1050; entry {\"block\":2,\"offset\":80,\"top\":900}; 0 written; nothing running",
    "a later change no longer moves the pane": "pane at 1050; entry {\"block\":2,\"offset\":80,\"top\":900}; 0 written; nothing running",
    "back again: the place waits for the page": "pane at 0; entry {\"block\":3,\"offset\":40,\"top\":2000}; 0 written; holding",
    "the reader moves first: the place is theirs": "pane at 0; entry {\"block\":3,\"offset\":40,\"top\":2000}; 0 written; nothing running",
    "the page paints: the pane is not moved": "pane at 0; entry {\"block\":3,\"offset\":40,\"top\":2000}; 0 written; nothing running",
    "back with the page there: the pane is placed at once": "pane at 1360; entry {\"block\":3,\"offset\":40,\"top\":2000}; 0 written; holding, settling",
    "the reader moves during the hold": "pane at 2500; entry {\"block\":3,\"offset\":40,\"top\":2000}; 0 written; write waiting",
    "a change after that does not undo it": "pane at 2500; entry {\"block\":3,\"offset\":40,\"top\":2000}; 0 written; write waiting",
    "and the reader's new place is written": "pane at 2500; entry {\"block\":3,\"offset\":580,\"top\":2500}; 1 written; nothing running",
    "an address with a fragment names its own place: the pane is left alone": "pane at 700; entry {\"block\":2,\"offset\":10,\"top\":900}; 0 written; nothing running",
    "back and forward between tabs: this tab's place": "pane at 1430; entry {\"block\":2,\"offset\":10,\"top\":900}; 0 written; holding, settling",
    "a write still waiting when history moves is dropped with the old entry": "pane at 1025; entry {\"block\":1,\"offset\":5,\"top\":400}; 0 written; holding, settling",
    "a page with fewer blocks than the place shows its last": "pane at 430; entry {\"block\":40,\"offset\":10,\"top\":90000}; 0 written; holding, settling",
    "what is not a place is no place: {\"block\":\"1\",\"offset\":0,\"top\":0}": "pane at 0; entry {\"block\":\"1\",\"offset\":0,\"top\":0}; 0 written; nothing running",
    "what is not a place is no place: {\"block\":1}": "pane at 0; entry {\"block\":1}; 0 written; nothing running",
    "what is not a place is no place: \"nonsense\"": "pane at 0; entry \"nonsense\"; 0 written; nothing running",
    "dispose ends all of it": "pane at 900; entry {\"block\":1,\"offset\":5,\"top\":400}; 0 written; nothing running",
    "a disposed keeper does nothing": "pane at 900; entry {\"block\":1,\"offset\":5,\"top\":400}; 0 written; nothing running"
  },
  "pageRoutes": [
    "/pull/7 is #7's conversation: true",
    "/pull/7/ is #7's conversation: true",
    "/pull/7/files is #7's files: true",
    "/pull/7/files/src/app.py is #7's files: true",
    "/pull/7/files/src/app.py is #7's conversation: false",
    "/pull/7/checks is #7's checks: true",
    "/pull/7/checks is #7's conversation: false",
    "/pull/7/checks/src/app.py is #7's checks: false",
    "/pull/70/files is #7's files: false",
    "/pull/7/filesx is #7's files: false",
    "/pull/8/files/src/app.py is #7's files: false"
  ]
}
? 0
```
The mounted PR heading starts with a decorative state glyph and keeps the state as a
text badge below the heading.
The production mount keeps the displayed comparison through waiting and failed repairs,
and remounts it once after success even if metadata has advanced to another head.
Pending and disposed controls cannot issue duplicate requests.
Asset and render failures retain their local Retry action.
Opening Changes beside a checkout starts an acquisition and offers Retry changes after a
refusal. The tabs answer to `C`, `G`, and `H` through the production shortcut registry
and plugin shortcut facade, with or without Shift and never with Ctrl: a tab the address
does not show opens through the route, as a click on its link does.
The keys wait while the tab column is out of the page before the record arrives, return
when the header puts it back, wait while the page is staged inert, and end with the
page.

```console
$ node tests/dom/github-pull-page-mount-behavior.js
{"titleStateAndTextBadge":true,"failedAssetsRecover":true,"failedRenderRecovers":true,"staleRetryIsInert":true,"checkoutFetchIsAutomatic":true,"displayedComparisonRepair":true,"bridgeAfterPaint":true,"bridgeFramesOwned":true,"hiddenReadiness":true,"markdownOwnership":true,"checkRows":true,"headerAges":true,"tabKeys":["before the record, the tab column out of the page: keys C G H, live none","C: not handled","the record arrives and paintHeader puts the column in: Conversation C, Changes G, Checks H","live: conversation files checks","C: showed Conversation","G: opened the files route","the route arrives: Changes","Shift+H: opened the checks route","Shift+C: opened the conversation route","Ctrl+G: not handled","staged inert: G: not handled","committed: G: opened the files route","disposed: Conversation none, Changes none, Checks none; keys none; G: not handled"]}
? 0
```

The selected and direct cold-page cases hold the POST until a description preview is
ready. It verifies plain text, explicit unfinished sections, no premature Markdown or
comparison actions, full-record priority, and cancellation without losing the previous
useful surface. Checks has its own route and loading state, and it retains the existing
check links and notices once the record is ready.

```console
$ node tests/dom/github-pull-core-preview-behavior.js
{"description":"plain preview before full conversation","pendingParts":["discussion","checks"],"checkResults":{"route":"/pull/7/checks","links":2,"empty":true,"pending":true},"waitCorePost":{"number":7,"retry":true,"wait_core":true},"previewMarkdownRequests":0,"fullMarkdownRequests":1,"fullRecordWins":true,"crossOwnerRetirement":true,"stagedReplacement":"A retained through B cancellation until C commits"}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

Conversation paints before its commit timeline request, which waits for nothing.
The timeline that answers once it has painted goes after everything painted, in its
order, moving no painted node and keeping the rendered Markdown and focus (`appended`).
A later first paint with that projection held, here the Conversation shown again after
another tab, places its commit summaries among the cards in provider order, keeping
unmatched and pending discussion (`interleaved`). The provider request breathes the
header’s age line and marks it busy; nothing spins.
A refreshed record keeps the rows it shows until its own timeline answers, and retires
them when that timeline answers with nothing (`supersededRowsRetired`). A kept commit
row tells its age as of each paint (`keptCommitRowsRetellAges`). A stale page can show a
held timeline before its metadata refresh.
A cache miss waits for metadata settlement before asking the provider, and an old
response cannot publish after a revision change or a tab switch.
An explicitly retryable provider failure can try again once while the reader stays.
A partial timeline and its focused commit link remain in place during the retry.

```console
$ node tests/dom/github-pull-timeline-session.js
{
  "interleaved": [
    "body",
    "issue_comment/9007199254740993",
    "<img> First commit",
    "review/9007199254740993",
    "Last commit",
    "review/3279967139",
    "review/15",
    "Some commits may be missing."
  ],
  "appended": [
    "<img> First commit",
    "Last commit",
    "Some commits may be missing."
  ],
  "destination": "https://github.com/octo/demo/pull/7/commits/0123456789012345678901234567890123456789",
  "heldMarkdownAndFocus": true,
  "lateCommitsMoveNothing": true,
  "staleCacheHitBeforeMetadata": true,
  "staleCacheMissWaited": true,
  "supersededReadAborted": true,
  "departedReadAborted": true,
  "unavailableKeepsDiscussion": true,
  "transientRetryIsBoundedAndKeepsPartial": true,
  "supersededRowsRetired": true,
  "keptCommitRowsRetellAges": true
}
? 0
```

## Conversation and Changes First Paints

The conversation’s first paint of a full record is laid out out of sight until the
Markdown of every text its first screen shows can be inserted, within
`DESCRIPTION_HOLD_MS`, and the page is not ready meanwhile (`firstVisit`, `comments`).
The first screen is the page’s own, measured from its top, not the view of a scrolled
page it replaces, and a text that comes into it as those above render is waited for too,
the next few past it asked for at once (`firstScreen`); a text it never waited for that
fails leaves the hold met.
Over the loading page the header waits with the body, so the loading heading and any
blocks that had shown stay where they were until both change once (`landing`,
`landingAfterBlocksShowed`), and a page replaced while held stays out of sight
(`cancelledWhileHeld`). A revisit and a refreshed record with the same text paint the
render kept for that text at once, keeping its node (`revisit`, `refreshedSameText`).
Past the bound the text shows plain and its Markdown follows (`pastTheBound`). The state
badge’s first paint is the fresher of the cached record and the repository’s list
(`listedState`). Changes with rendered Markdown stays out of sight until its first
screen settles or `CHANGES_FIRST_SCREEN_MS` passes (`changes`). The kept renders are
bounded by count and by characters, descriptions apart from other parts (`bounded`).

```console
$ node tests/dom/github-pull-first-paint-behavior.js
{
  "firstVisit": "held, then final",
  "refreshedSameText": "kept",
  "revisit": "final at first paint",
  "pastTheBound": "plain, then Markdown",
  "comments": {
    "texts": 5,
    "asked": 5,
    "plainAtReady": 0
  },
  "holdSpans": [
    "hidden met 1",
    "hidden bound 1"
  ],
  "landing": {
    "blocksBefore": true,
    "whileHeld": {
      "holding": true,
      "blocks": false,
      "heading": "Pull request #7"
    },
    "final": true,
    "heading": "Count to two in the app #7"
  },
  "landingAfterBlocksShowed": {
    "whileHeld": {
      "holding": true,
      "sameBlocks": true,
      "cover": true,
      "heading": "Pull request #7"
    },
    "shown": {
      "blocks": false,
      "holding": false,
      "final": true,
      "heading": "Count to two in the app #7"
    }
  },
  "cancelledWhileHeld": {
    "holding": true
  },
  "firstScreen": {
    "0": {
      "plainOnFirstScreenAtReady": [],
      "waitedFor": 3,
      "outcome": "met",
      "askedBeforeSecondAnswer": 3
    },
    "5000": {
      "plainOnFirstScreenAtReady": [],
      "waitedFor": 3,
      "outcome": "met",
      "askedBeforeSecondAnswer": 3
    },
    "failsPastTheScreen": {
      "plainOnFirstScreenAtReady": [],
      "waitedFor": 2,
      "outcome": "met",
      "askedBeforeSecondAnswer": 4
    },
    "cascade": {
      "plainOnFirstScreenAtReady": [],
      "waitedFor": 6,
      "outcome": "met",
      "rounds": 4
    }
  },
  "ages": [
    "186 min",
    "185 min",
    "4 min"
  ],
  "listedState": {
    "newerList": "Merged",
    "olderList": "Open"
  },
  "changes": {
    "settled": {
      "asked": 200,
      "held": true,
      "readyWhileHeld": false,
      "shown": true,
      "ready": true,
      "holdingAtJump": true
    },
    "bound": {
      "asked": 200,
      "held": true,
      "readyWhileHeld": false,
      "shown": true,
      "ready": true,
      "holdingAtJump": true
    }
  },
  "bounded": true
}
? 0
```
