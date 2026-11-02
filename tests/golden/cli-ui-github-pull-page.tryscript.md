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
An absent record offers a fetch and a stale one a refresh, each through
`POST /api/plugin/github/pull-refresh`. The Markdown of each text is asked for one part
at a time from `/api/plugin/github/pull-markdown`, two at once, and a render of a record
the page no longer shows is dropped.

This browserless session loads the production `builtin_plugins/github/pull-page.js` and
plays the server’s side from `tests/fixtures/github-pull-page-responses.json`: what the
in-process application answered while it served pull request 7 of the stand-in in
`tests/github_pull_fixture.py`, from nothing cached, through a fetch, to a stale record
and a refresh that brought one more comment.
`tests/test_github_pull_page_session.py` replays that story and fails when the recording
drifts. Timers, the clock, visibility, and paint are injected; the browser’s visibility
observer is played by asking for parts in reading order.
`states` is the header in github.com’s words and the checks as GitHub counts them for
the open pull request and for the stand-in’s merged and closed ones, which the same
server answered: “wants to merge” with the commit count until it is merged, then the
account that merged it, or no one when the record names no merger, and skipped checks
apart from neutral ones.
Pull requests 7 and 9 come from forks, so both sides carry their owner, as in
github.com’s “into cli:trunk from 00200200:fix/…”; pull request 8 is from the same
repository, so both sides are bare branch names.
The last lines show which links a rendered text keeps (made absolute against the pull
request’s github.com page, http and https only), and the `/view/` address a review
comment’s file opens at.
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
        "status": "absent",
        "tab": "conversation",
        "message": "No data for this pull request is cached yet.",
        "canRefresh": true,
        "freshness": null,
        "failure": null,
        "header": null,
        "labels": [],
        "merge": null,
        "timeline": [],
        "reviewComments": [],
        "checks": null,
        "notes": [],
        "headOffer": null,
        "comparison": null
      },
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
      "step": "fetch it",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true}"
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
        "freshness": "Fetched just now by gh:octo-reader",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits into octo:topic from forker:count-to-two",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch",
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
            "[success] tests (3.13) -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo -> https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "headOffer": "This page's code is c691256511d0, not the pull request's head 85fcb2fa9e77. [Switch to the head] -> refs/pull/7/head",
        "comparison": "f92fd713acd5...85fcb2fa9e77 (head moved)"
      },
      "conversation": "repaint",
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
      "step": "switch the pin to the head the record names",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/pull/7/head\"}"
      ],
      "timer": "slow",
      "paints": 0,
      "reloads": 1,
      "markdown": []
    },
    {
      "step": "reloaded on the head, nothing is offered",
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
        "freshness": "Fetched just now by gh:octo-reader",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits into octo:topic from forker:count-to-two",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch",
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
            "[success] tests (3.13) -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo -> https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "open Files changed",
      "requests": [],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "current",
        "tab": "files",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now by gh:octo-reader",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits into octo:topic from forker:count-to-two",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch",
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
            "[success] tests (3.13) -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo -> https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
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
        "freshness": "Fetched just now by gh:octo-reader",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits into octo:topic from forker:count-to-two",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch",
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
            "[success] tests (3.13) -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo -> https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "the record goes stale: the page asks for a refresh by itself",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)",
        "POST /api/plugin/github/pull-refresh {\"number\":7}"
      ],
      "timer": "fast",
      "paints": 2,
      "paint": {
        "status": "stale",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Refreshing… · fetched 5 min ago by gh:octo-reader",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits into octo:topic from forker:count-to-two",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch",
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
            "[success] tests (3.13) -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo -> https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
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
        "freshness": "Fetched just now by gh:octo-reader",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits into octo:topic from forker:count-to-two",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch",
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
            "[success] tests (3.13) -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo -> https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
        "headOffer": null,
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "reask",
      "markdown": []
    },
    {
      "step": "a render of the older record is dropped",
      "requests": [
        "GET /api/plugin/github/pull-markdown?number=7&part=body"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
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
        "freshness": "Fetched just now by gh:octo-reader",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits into octo:topic from forker:count-to-two",
        "labels": [
          "enhancement"
        ],
        "merge": "No conflicts with the base branch",
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
            "[success] tests (3.13) -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654787",
            "[in progress] docs -> https://github.com/octo/demo/actions/runs/18062895276/job/51401654788",
            "[success] docs/readthedocs.org:demo -> https://demo--7.org.readthedocs.build/en/7/"
          ]
        },
        "notes": [],
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
        "freshness": "Fetched 5 min ago by gh:octo-reader · may be out of date",
        "failure": null,
        "headOffer": null
      },
      "markdown": []
    },
    {
      "step": "shown, it asks for its refresh",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)",
        "POST /api/plugin/github/pull-refresh {\"number\":7}"
      ],
      "timer": "fast",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Refreshing… · fetched 5 min ago by gh:octo-reader",
        "failure": null,
        "headOffer": null
      },
      "markdown": []
    },
    {
      "step": "a stale page asks once, and its refresh is not due",
      "requests": [
        "GET /api/plugin/github/pull?number=8",
        "POST /api/plugin/github/pull-refresh {\"number\":8}"
      ],
      "timer": "slow",
      "paints": 2,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": true,
        "freshness": "Fetched 24 min ago by gh:octo-reader · may be out of date",
        "failure": "The last refresh failed: gh could not reach api.github.com",
        "headOffer": "refs/pull/8/head"
      },
      "conversation": "repaint",
      "markdown": []
    },
    {
      "step": "its next poll asks nothing",
      "requests": [
        "GET /api/plugin/github/pull?number=8"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "shown again, it may ask once more",
      "requests": [
        "GET /api/plugin/github/pull?number=8 (If-None-Match)",
        "POST /api/plugin/github/pull-refresh {\"number\":8}"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "a reader's Refresh is always taken",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":8,\"retry\":true}"
      ],
      "timer": "fast",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": false,
        "freshness": "Refreshing… · fetched 24 min ago by gh:octo-reader",
        "failure": null,
        "headOffer": "refs/pull/8/head"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "an address alone reads what is cached",
      "requests": [
        "GET /api/plugin/github/pull?number=14"
      ],
      "timer": "slow",
      "paints": 2,
      "paint": {
        "status": "absent",
        "message": "No data for this pull request is cached yet.",
        "canRefresh": true,
        "freshness": null,
        "failure": null,
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
        "POST /api/plugin/github/pull-refresh {\"number\":14,\"retry\":true}"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "absent",
        "message": "The refresh was refused (too many pull requests are being fetched; try again when one has finished).",
        "canRefresh": true,
        "freshness": null,
        "failure": null,
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
        "status": "absent",
        "tab": "conversation",
        "message": "No data for this pull request is cached yet.",
        "canRefresh": true,
        "freshness": null,
        "failure": null,
        "header": null,
        "labels": [],
        "merge": null,
        "timeline": [],
        "reviewComments": [],
        "checks": null,
        "notes": [],
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
      "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits into octo:topic from forker:count-to-two",
      "checks": {
        "success": 2,
        "pending": 1
      }
    },
    "merged": {
      "header": "Say more in the guide #8 [Merged] octo merged 1 commit into topic from guide-more",
      "checks": {
        "success": 2,
        "skipped": 1
      }
    },
    "closed": {
      "header": "spam #9 [Closed] ghost wants to merge 1 commit into octo:topic from spam (deleted fork)",
      "checks": {
        "success": 2,
        "pending": 1
      }
    },
    "merged_unattributed": {
      "header": "Say more in the guide #8 [Merged] merged 1 commit into topic from guide-more",
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
  ],
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
      "earlier": "2 lines: @@ -1,30 +1,30 @@ def main(): ...  line 22",
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
      "earlier": "25 lines: @@ -1,30 +1,30 @@ def main(): ...  line 23",
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
      "earlier": "14 lines: @@ -1,30 +1,30 @@ def main(): ...  line 13",
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
      "earlier": "15 lines: @@ -1,30 +1,30 @@ def main(): ...  line 14",
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
      "earlier": "14 lines: @@ -1,30 +1,30 @@ def main(): ...  line 13",
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
  }
}
? 0
```
