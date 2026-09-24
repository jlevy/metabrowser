---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Pull-Request Page

The served pull request’s page at `/pull/<n>` renders the cached record the GitHub
plugin’s pull route answers: header, state, merge status, labels, the conversation with
review states, review comments with their file, line, and diff hunk, checks, and notes.
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
The last lines show a page for a number the server does not serve, which links a
rendered text keeps (made absolute against the pull request’s github.com page, http and
https only), and the `/view/` address a review comment’s file opens at.

```console
$ node tests/dom/github-pull-page-session.js
{
  "steps": [
    {
      "step": "open with nothing cached",
      "requests": [
        "GET /api/plugin/github/pull"
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
        "GET /api/plugin/github/pull (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "fetch it",
      "requests": [
        "POST /api/plugin/github/pull-refresh {}"
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
        "GET /api/plugin/github/pull"
      ],
      "timer": "fast",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "the record arrives",
      "requests": [
        "GET /api/plugin/github/pull (If-None-Match)"
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
        "header": "Count to two in the app #7 [Open] forker: topic <- forker:count-to-two",
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
        "GET /api/plugin/github/pull-markdown?part=body",
        "GET /api/plugin/github/pull-markdown?part=issue_comment%2F3341937855"
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
        "GET /api/plugin/github/pull-markdown?part=review%2F3279967139",
        "GET /api/plugin/github/pull-markdown?part=review_comment%2F2383608906"
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
        "GET /api/plugin/github/pull-markdown?part=issue_comment%2F1"
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
        "GET /api/plugin/github/pull (If-None-Match)"
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
        "header": "Count to two in the app #7 [Open] forker: topic <- forker:count-to-two",
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
        "header": "Count to two in the app #7 [Open] forker: topic <- forker:count-to-two",
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
        "header": "Count to two in the app #7 [Open] forker: topic <- forker:count-to-two",
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
      "step": "the record goes stale",
      "requests": [
        "GET /api/plugin/github/pull (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "stale",
        "tab": "conversation",
        "message": null,
        "canRefresh": true,
        "freshness": "Fetched 5 min ago by gh:octo-reader · may be out of date",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker: topic <- forker:count-to-two",
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
      "step": "refresh the stale page",
      "requests": [
        "POST /api/plugin/github/pull-refresh {}"
      ],
      "timer": "fast",
      "paints": 1,
      "paint": {
        "status": "stale",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Refreshing… · fetched 5 min ago by gh:octo-reader",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker: topic <- forker:count-to-two",
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
        "GET /api/plugin/github/pull"
      ],
      "timer": "fast",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "a refresh that changed no text keeps the conversation",
      "requests": [
        "GET /api/plugin/github/pull (If-None-Match)"
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
        "header": "Count to two in the app #7 [Open] forker: topic <- forker:count-to-two",
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
        "GET /api/plugin/github/pull-markdown?part=body"
      ],
      "timer": "slow",
      "paints": 0,
      "markdown": []
    },
    {
      "step": "another refresh brought a comment full of markup",
      "requests": [
        "GET /api/plugin/github/pull (If-None-Match)"
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
        "header": "Count to two in the app #7 [Open] forker: topic <- forker:count-to-two",
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
        "GET /api/plugin/github/pull-markdown?part=issue_comment%2F3341937856"
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
        "GET /api/plugin/github/pull (If-None-Match)"
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
      "step": "a page opened in the background reads once",
      "requests": [
        "GET /api/plugin/github/pull"
      ],
      "timer": null,
      "paints": 2,
      "paint": {
        "status": "current",
        "tab": "files",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now by gh:octo-reader",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker: topic <- forker:count-to-two",
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
      "markdown": []
    }
  ],
  "otherNumber": {
    "status": "other_number",
    "message": "This server serves pull request #7.",
    "served": 7
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
