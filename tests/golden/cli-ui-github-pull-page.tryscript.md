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
A page served an older head of this pull request offers nothing: the server follows the
head, as it follows a branch, and the recording’s answer after such a refresh names the
new head as its pin.

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
A place in the header goes no further than the first block, since a page opened again
draws its header closed, and an open Diff summary made it far taller.
It asserts, and so prints nothing for, that no pace of moves writes a place more often
than Safari’s limit on `history.replaceState`, and that only a key that can move the
pane ends a hold. In Changes a place names its file, so a diff that replaces the one
being read, a newer head’s, holds the reader in that file wherever it now is, and at its
index only when the new diff has no such file.
`filesChanged` is what Changes does with the record’s comparison: it follows one that
moved, and offers it instead to a reader who went back to the earlier diff.
`changesFollowed` is the line Changes then says, the head it showed and the head it
shows with the way back, on the page and after the reload a followed pin makes, where
the history entry remembers what Changes showed.

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
      "askWaits": true,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement #2700af --github-label-r:39;--github-label-g:0;--github-label-b:175;--github-label-h:253;--github-label-s:100;--github-label-l:34 tip: A label's description is its chip's tooltip"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer 2026-09-16T12:32:50Z review/3274109685",
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
      "askWaits": true,
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
      "askWaits": true,
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
      "askWaits": true,
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
      "askWaits": true,
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
      "askWaits": true,
      "markdown": []
    },
    {
      "step": "Browse code that the server refuses says why and stays",
      "requests": [
        "POST /api/source/pin {\"oid\":\"85fcb2fa9e77eb5db485ffef445cbbc645d6db4a\",\"under\":\"refs/pull/7/head\",\"view\":\"/view/\"}"
      ],
      "timer": "slow",
      "paints": 1,
      "askWaits": true,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": "This commit is not on the origin.",
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement #2700af --github-label-r:39;--github-label-g:0;--github-label-b:175;--github-label-h:253;--github-label-s:100;--github-label-l:34 tip: A label's description is its chip's tooltip"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer 2026-09-16T12:32:50Z review/3274109685",
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
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "Browse code serves the head and opens the root",
      "requests": [
        "POST /api/source/pin {\"oid\":\"85fcb2fa9e77eb5db485ffef445cbbc645d6db4a\",\"under\":\"refs/pull/7/head\",\"view\":\"/view/\"}"
      ],
      "timer": "slow",
      "paints": 0,
      "askWaits": true,
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
      "askWaits": true,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement #2700af --github-label-r:39;--github-label-g:0;--github-label-b:175;--github-label-h:253;--github-label-s:100;--github-label-l:34 tip: A label's description is its chip's tooltip"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer 2026-09-16T12:32:50Z review/3274109685",
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
      "askWaits": true,
      "markdown": []
    },
    {
      "step": "open Changes",
      "requests": [],
      "timer": "slow",
      "paints": 1,
      "askWaits": true,
      "paint": {
        "status": "current",
        "tab": "files",
        "message": null,
        "canRefresh": true,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement #2700af --github-label-r:39;--github-label-g:0;--github-label-b:175;--github-label-h:253;--github-label-s:100;--github-label-l:34 tip: A label's description is its chip's tooltip"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer 2026-09-16T12:32:50Z review/3274109685",
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
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "markdown": []
    },
    {
      "step": "back to the conversation",
      "requests": [],
      "timer": "slow",
      "paints": 1,
      "askWaits": true,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement #2700af --github-label-r:39;--github-label-g:0;--github-label-b:175;--github-label-h:253;--github-label-s:100;--github-label-l:34 tip: A label's description is its chip's tooltip"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer 2026-09-16T12:32:50Z review/3274109685",
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
          "enhancement #2700af --github-label-r:39;--github-label-g:0;--github-label-b:175;--github-label-h:253;--github-label-s:100;--github-label-l:34 tip: A label's description is its chip's tooltip"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer 2026-09-16T12:32:50Z review/3274109685",
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
        "comparison": "f92fd713acd5...85fcb2fa9e77"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "the reader stayed: the page asks for a refresh by itself",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"07eb0c3ec47a9c84c4d0b69ddfca32245cdede7023567fa7d179789783e8d66b\"}"
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
          "enhancement #2700af --github-label-r:39;--github-label-g:0;--github-label-b:175;--github-label-h:253;--github-label-s:100;--github-label-l:34 tip: A label's description is its chip's tooltip"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer 2026-09-16T12:32:50Z review/3274109685",
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
      "probeAskMs": 5000,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement #2700af --github-label-r:39;--github-label-g:0;--github-label-b:175;--github-label-h:253;--github-label-s:100;--github-label-l:34 tip: A label's description is its chip's tooltip"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer 2026-09-16T12:32:50Z review/3274109685",
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
      "probeAskMs": 5000,
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
      "probeAskMs": 5000,
      "paint": {
        "status": "current",
        "tab": "conversation",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "header": "Count to two in the app #7 [Open] forker wants to merge 2 commits: forker:count-to-two → octo:topic",
        "labels": [
          "enhancement #2700af --github-label-r:39;--github-label-g:0;--github-label-b:175;--github-label-h:253;--github-label-s:100;--github-label-l:34 tip: A label's description is its chip's tooltip"
        ],
        "merge": "No conflicts with the base branch.",
        "timeline": [
          "review maintainer 2026-09-16T12:32:50Z review/3274109685",
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
      "probeAskMs": 5000,
      "markdown": [
        "issue_comment/3341937856: <div><div><p>Rebased on <code>topic</code>; see <a href=\"https://github.com/octo/demo/pull/docs/new.md\" target=\"_blank\" rel=\"noopener noreferrer\">the docs</a>.</p>\n\n<img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://example.com/badge.png\" alt=\"build badge\"> <span class=\"mb-image-fallback\">image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p></div></div>"
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
      "probeAskMs": 5000,
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
        "browse": "link to the root"
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
        "browse": "link to the root"
      },
      "markdown": []
    },
    {
      "step": "the reader stayed: it asks",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"07eb0c3ec47a9c84c4d0b69ddfca32245cdede7023567fa7d179789783e8d66b\"}"
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
        "browse": "link to the root"
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
        "browse": "link to the root"
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
      "step": "the served head followed the pull request, and nothing is offered",
      "requests": [
        "GET /api/plugin/github/pull?number=7"
      ],
      "timer": "slow",
      "paints": 2,
      "askWaits": true,
      "paint": {
        "status": "current",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "browse": "link to the root"
      },
      "conversation": "repaint",
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
        "failure": "Could not reach GitHub.",
        "browse": null
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
        "message": "The refresh could not start while other pull requests are being fetched.",
        "canRefresh": true,
        "freshness": null,
        "failure": "Could not reach GitHub.",
        "browse": null
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
  "pageDefense": "<p>Rebased on <code>topic</code>; see <a href=\"https://github.com/octo/demo/pull/docs/new.md\" target=\"_blank\" rel=\"noopener noreferrer\">the docs</a>.</p>\n\n<img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://example.com/badge.png\" alt=\"build badge\"></img> <span class=\"mb-image-fallback\">image</span>\n<a href=\"https://example.com/x\" target=\"_blank\" rel=\"noopener noreferrer\">x</a>\n\n<div>video</div><span>copy</span><div>fake dialog</div><p>styled</p>",
  "filesChanged": [
    "nothing open yet: mount",
    "open on the record's comparison: keep",
    "open on an older head: follow",
    "open on an older head the reader went back to: offer",
    "no comparison in the record: unavailable"
  ],
  "changesFollowed": {
    "the first diff of a page": "no note",
    "a newer head replaces the diff shown": "Changes now show this pull request’s newer commits. [Show the earlier changes] -> f92fd71...c691256",
    "the same diff mounted again keeps its note": "Changes now show this pull request’s newer commits. [Show the earlier changes] -> f92fd71...c691256",
    "a second head names the one before it": "Changes now show this pull request’s newer commits. [Show the earlier changes] -> f92fd71...85fcb2f",
    "the same head from another base": "The comparison has changed. [Show the earlier changes] -> bbbbbbb...85fcb2f",
    "the page loaded again on the newer head, its entry remembering the earlier diff": "Changes now show this pull request’s newer commits. [Show the earlier changes] -> f92fd71...c691256",
    "the page loaded again after it had followed": "Changes now show this pull request’s newer commits. [Show the earlier changes] -> f92fd71...c691256",
    "an entry that last showed this diff and no other": "no note"
  }
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
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"07eb0c3ec47a9c84c4d0b69ddfca32245cdede7023567fa7d179789783e8d66b\"}"
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
        "browse": "link to the root"
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
      "probeAskMs": 5000,
      "paint": {
        "status": "current",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "browse": "link to the root"
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
        "browse": "link to the root"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "it asks for the next refresh at once",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"582fab3059ef946c580b6d665726b7cd0072175616a0a4eded448d06c83c011a\"}"
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
        "browse": "link to the root"
      },
      "conversation": "keep",
      "markdown": []
    }
  ],
  "probing": [
    {
      "step": "a current page asks once the reader stays, and a probe answers",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"582fab3059ef946c580b6d665726b7cd0072175616a0a4eded448d06c83c011a\"}"
      ],
      "timer": "slow",
      "paints": 0,
      "probeAskMs": 5000,
      "markdown": []
    },
    {
      "step": "its interval later it asks again, and the probe vouches",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"582fab3059ef946c580b6d665726b7cd0072175616a0a4eded448d06c83c011a\"}"
      ],
      "timer": "slow",
      "paints": 0,
      "probeAskMs": 5000,
      "markdown": []
    },
    {
      "step": "the poll's own interval still reads, between probe asks",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)"
      ],
      "timer": "slow",
      "paints": 0,
      "probeAskMs": 5000,
      "markdown": []
    },
    {
      "step": "a probe ask the server does not answer is reported",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"582fab3059ef946c580b6d665726b7cd0072175616a0a4eded448d06c83c011a\"}"
      ],
      "timer": "slow",
      "paints": 1,
      "probeAskMs": 5000,
      "paint": {
        "status": "current",
        "message": "The server did not answer.",
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "browse": "link to the root"
      },
      "conversation": "repaint",
      "markdown": []
    },
    {
      "step": "the next probe ask that answers clears it",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"582fab3059ef946c580b6d665726b7cd0072175616a0a4eded448d06c83c011a\"}"
      ],
      "timer": "slow",
      "paints": 1,
      "probeAskMs": 5000,
      "paint": {
        "status": "current",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched just now via GitHub CLI",
        "failure": null,
        "browse": "link to the root"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "an answer slower than the interval is followed by a short gap",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"582fab3059ef946c580b6d665726b7cd0072175616a0a4eded448d06c83c011a\"}"
      ],
      "timer": "slow",
      "paints": 0,
      "probeAskMs": 1000,
      "markdown": []
    },
    {
      "step": "hidden, it asks nothing",
      "requests": [],
      "timer": null,
      "paints": 0,
      "markdown": []
    },
    {
      "step": "shown again past its interval it asks at once, and a probe that found a change refreshes",
      "requests": [
        "GET /api/plugin/github/pull?number=7 (If-None-Match)",
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"582fab3059ef946c580b6d665726b7cd0072175616a0a4eded448d06c83c011a\"}"
      ],
      "timer": "fast",
      "paints": 2,
      "paint": {
        "status": "current",
        "message": null,
        "canRefresh": false,
        "freshness": "Fetched 6 min ago via GitHub CLI",
        "revalidating": true,
        "failure": null,
        "browse": "link to the root"
      },
      "conversation": "keep",
      "markdown": []
    }
  ],
  "failing": [
    {
      "step": "a stale page asks once, and its refresh is not due",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":8,\"held\":\"6ceee0aed2478da7996fe0a4188bf097437bda8dc70e1f0e897043f9c3dbcbc5\"}"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": true,
        "freshness": "Fetched 24 min ago via GitHub CLI",
        "failure": "Could not reach GitHub.",
        "browse": "switches to refs/pull/8/head"
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
        "failure": "Could not reach GitHub.",
        "browse": "switches to refs/pull/8/head"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "that ask is sent with no wait, and is not due",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":8,\"held\":\"6ceee0aed2478da7996fe0a4188bf097437bda8dc70e1f0e897043f9c3dbcbc5\"}"
      ],
      "timer": "slow",
      "paints": 1,
      "paint": {
        "status": "stale",
        "message": null,
        "canRefresh": true,
        "freshness": "Fetched 25 min ago via GitHub CLI",
        "failure": "Could not reach GitHub.",
        "browse": "switches to refs/pull/8/head"
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
        "browse": "switches to refs/pull/8/head"
      },
      "conversation": "keep",
      "markdown": []
    }
  ],
  "rateLimited": [
    {
      "step": "a stale page asks for its refresh",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"07eb0c3ec47a9c84c4d0b69ddfca32245cdede7023567fa7d179789783e8d66b\"}"
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
        "browse": "link to the root"
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
        "failure": "GitHub rate limit reached. Next attempt after 12:06 PM.",
        "browse": "link to the root"
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
        "failure": "GitHub rate limit reached. Next attempt after 12:06 PM.",
        "browse": "link to the root"
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
        "failure": "GitHub rate limit reached. Next attempt after 12:06 PM.",
        "browse": "link to the root"
      },
      "conversation": "keep",
      "markdown": []
    },
    {
      "step": "and sends that ask with no wait",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":7,\"held\":\"07eb0c3ec47a9c84c4d0b69ddfca32245cdede7023567fa7d179789783e8d66b\"}"
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
        "browse": "link to the root"
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
      "files": "Changes could not be shown.",
      "notes": [
        "Changes could not be loaded."
      ]
    },
    "no_merge_base": {
      "files": "Changes cannot be shown because this pull request’s branches share no history.",
      "notes": [
        "Changes could not be loaded."
      ]
    },
    "base_uncertain": {
      "files": "Changes need more of this checkout’s history. Refresh to fetch it.",
      "notes": [
        "Changes could not be loaded."
      ]
    },
    "commits_unavailable": {
      "files": "Changes need commits that are missing here. Refresh to fetch them.",
      "notes": [
        "Changes could not be loaded."
      ]
    },
    "no_store": {
      "files": "Changes could not be fetched.",
      "notes": []
    },
    "comparison_timeout": {
      "files": "Changes took too long to prepare. Refresh to try again.",
      "notes": [
        "Changes could not be loaded."
      ]
    },
    "comparison_too_large": {
      "files": "Changes are too large to show here. GitHub shows them.",
      "notes": [
        "Changes could not be loaded."
      ]
    }
  },
  "checkout": {
    "HEAD is the pull request's head": {
      "browse": null,
      "checkoutAtHead": "This checkout’s HEAD is this pull request’s head.",
      "comparison": null,
      "files": "Changes could not be fetched."
    },
    "HEAD is elsewhere": {
      "browse": null,
      "checkoutAtHead": null,
      "comparison": null,
      "files": "Changes could not be fetched."
    },
    "no repository context": {
      "browse": null,
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
    "a place in a header now shorter shows the first block": "pane at 120; entry {\"block\":-1,\"offset\":0,\"top\":30000}; 0 written; holding, settling",
    "what is not a place is no place: {\"block\":\"1\",\"offset\":0,\"top\":0}": "pane at 0; entry {\"block\":\"1\",\"offset\":0,\"top\":0}; 0 written; nothing running",
    "what is not a place is no place: {\"block\":1}": "pane at 0; entry {\"block\":1}; 0 written; nothing running",
    "what is not a place is no place: \"nonsense\"": "pane at 0; entry \"nonsense\"; 0 written; nothing running",
    "in Changes a place names its file": "pane at 460; entry {\"block\":1,\"offset\":40,\"top\":460,\"file\":\"b.py\"}; 1 written; nothing running",
    "the diff is replaced: the place is held, and written for a reload": "pane at 0; entry {\"block\":1,\"offset\":40,\"top\":460,\"file\":\"b.py\"}; 1 written; holding",
    "the emptied pane clamps to its top: the place stays written": "pane at 0; entry {\"block\":1,\"offset\":40,\"top\":460,\"file\":\"b.py\"}; 0 written; holding",
    "the newer diff paints: the pane is in the same file, a block further on": "pane at 710; entry {\"block\":1,\"offset\":40,\"top\":460,\"file\":\"b.py\"}; 0 written; holding, settling",
    "a file above it draws its lines: the pane is put back": "pane at 1310; entry {\"block\":1,\"offset\":40,\"top\":460,\"file\":\"b.py\"}; 0 written; holding, settling",
    "loaded again on a diff without the file: the top of the block at its index": "pane at 370; entry {\"block\":1,\"offset\":40,\"top\":460,\"file\":\"b.py\"}; 0 written; holding, settling",
    "a place whose file is not a name is no place": "pane at 0; entry {\"block\":1,\"offset\":5,\"top\":400,\"file\":7}; 0 written; nothing running",
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
    "/pull/7/docs is #7's docs: true",
    "/pull/7/docs is #7's conversation: false",
    "/pull/7/docs/README.md is #7's docs: false",
    "/pull/70/files is #7's files: false",
    "/pull/7/filesx is #7's files: false",
    "/pull/8/files/src/app.py is #7's files: false"
  ],
  "diffTabs": [
    "guided: false",
    "the front page: false",
    "conversation: false",
    "docs: true",
    "files: true",
    "checks: false"
  ],
  "docsEmpty": [
    "no changed document: true",
    "one changed document: false",
    "no manifest: false"
  ],
  "docsOffered": [
    "two documents: true",
    "no document: false",
    "no document listed of a cut-short list: null",
    "no docs row: null",
    "no counts: null"
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
refusal. The header has the same rows in the same order for every pull request and tab,
and while its record is on its way, but for the labels row, which a pull request with no
labels does not have, and the status line, which is there only for a failure, a message,
or an offer, and says it: a rate limit’s hold, and a server with no GitHub repository,
are said in the freshness note’s place, which ends the author’s row.
The state row holds a chip’s height with a strut, a stack has its slot at the end of the
author’s row, and Refresh, a text action, at the end of the row of ages.
The freshness note’s slot is as wide as its widest age: each age is put at “59 min ago”
for the copy that sizes it, and an unknown age sizes its own (`widestNotes`). A rate
limit’s hold says when it lifts as a time of day when that is today, and as a short date
and time when not (`holdLifts`). A comparison’s refusal is said in the Changes body, so
the header’s rows are the same on every tab while it stands.
The header’s last row, its Diff summary, holds the shell’s pending placeholder, the
navigation tally’s block after the quiet period, while a comparison is on its way and
while it is read: from the first paint of a page whose read will bring one, before its
first answer and through the absence its own fetch fills (mb-30dz), from a core preview
whose read prepares it, the same node through its record to the read, and from a record
whose comparison the page asked to prepare, on Conversation and on Checks, and on
Changes the mounted diff’s; the summary takes its place, and once the browser is idle
again the page asks for the first screen’s rendered Markdown itself, under a signal its
leaving aborts. While the comparison is on its way or read, the row holds the cached
changed-files list’s brief line in the placeholder’s place, the Pulls row’s sums with
the file count, once the page knows the head, and only a list of that head and its base,
the record’s comparison’s base commit or the base branch (mb-z8ea): from the Pulls rows’
memory with no read when nothing said the row’s list changed, else one read as the page
mounts; the summary replaces it, a read that fails keeps it, a list of another head or
base is not drawn, so the placeholder waits, and a page that went draws nothing more.
A list that only adds lines leaves its zero total out, “1 A, 2 M · +3,893”, as every
lines summary does (mb-ox6a). The same pull request opened again in the document draws
its summary from the kept comparison as the page mounts, with no read and no
placeholder, and so does one first opened on Changes, whose diff read through the same
keep (mb-neg9). A read that fails, a comparison the summary draws nothing for, a Changes
diff that reads no comparison, a pull request that is not GitHub’s, a refresh that
failed with nothing running, a record that names no comparison and has none coming, a
core preview whose read prepares none, and a preparation that ended with none leave the
row empty; a newer comparison on Changes is followed, which starts its read, and the way
back to the earlier diff and the offer of the newer one start theirs, as a Retry or the
page’s next paint after a read that failed starts the wait again; a record that then
names no comparison takes Changes’ diff away, and its wait with it (`headerSummary`). A
page mounted with no record in hand holds its header and tab column for the quiet
period, the first header with a record lifts the hold, a record that lands while the
header waits for the conversation’s held first paint keeps them unseen until that paint,
and a page with its record in hand holds nothing; the cold header’s title is “Pull
request #7” unless the Pulls tab’s row for it is in hand, when it has the record’s shape
with the row’s state and title, and a number two repositories’ rows name titles none
(`coldHold`). The header’s corner, right after the title from the cold header on, holds
the View on GitHub button: one corner for the page’s life, and after each header paint
the page asks the SDK for the button of the address it is at, the tab’s own address, and
an SDK with no button leaves the corner empty (`counterpart`). The tabs answer to `C`,
`G`, and `E` through the production shortcut registry and plugin shortcut facade, with
or without Shift and never with Ctrl: a tab the address does not show opens through the
route, as a click on its link does.
`H` is the Commits tab’s, so it does nothing here.
The header keeps the tab column unless its first read fails: while the record is on its
way, and for an absent record nothing is fetching, such as a server with no GitHub
repository. So the keys are live from first paint, as the links are, and a key asks for
the route a click on its link asks for.
The header’s links and actions are numbered by their place through the same facade, in
document order, which the stand-in DOM keeps as a page does, so Refresh, ending the row
of ages, comes after Browse code; the corner’s View on GitHub is not numbered.
Each number runs what its control does in the paint on screen, recorded as what the page
asked for: `1` asks to serve the head for Browse code, and on Changes `2` asks for a
refresh. A refresh that serves the head repaints Browse code as a link, and `1` then
opens the code instead; one with no pin drops Browse code, Refresh moves up to `1`, and
`2` reaches nothing.
Code served on the pull request’s head numbers no switch to it, since the server follows
that head: while the refresh `2` asks for runs, Refresh waits, shown and disabled, and
keeps `2`, so a second `2` asks nothing.
Once the refresh ends Refresh is offered again on Changes; on Conversation, where
nothing is left to refresh, Refresh is not shown.
The tab keys wait while the column is out of the page after a failed first read; they
return when the header puts it back, badged at once while Shift is held, wait while the
page is staged inert, and end with the page.
The failed first read here is followed on Changes, which holds no first paint, so it is
paintHeader’s own retarget that badges the returning links.
A text’s Mermaid blocks are drawn as github.com draws them, in the description and in a
comment alike, each as an image, since a text is untrusted, through the Markdown
plugin’s published host, which a page asks for only once a text has a block
(`textDiagrams`). A folder’s page draws them as a pinned revision’s does: on either,
each binding’s Mermaid is the Markdown plugin’s diagram frame’s, whose own policy bounds
what Mermaid loads while it lays a diagram out, and never the page’s. A poll of the same
record and a trip to Changes keep a text’s binding, an edited text’s ends with its
section, one replaced before the plugin arrives never binds, and the page’s end ends the
rest. The Diff summary’s wait is one the event log hears of if it runs late
(`eventLogDetails`, mb-9zp5): the page asks for the `event-reports` bundle on demand and
names the wait, timed from when it began.
At the late threshold the placeholder gives way to a line that says how long the summary
has not arrived, with a Details button that controls the panel it opens as the header’s
last row; the panel reads the event log for this page’s client ID, and closes with
Details or with its control, as when the summary arrives.
A page left while it waits ends the wait as `never_completed`; one whose summary arrives
ends it `ok`. A failed refresh’s Details read the failures from an hour before it ended
to a minute after, and with no reporter the panel says the event log is not available.

```console
$ node tests/dom/github-pull-page-mount-behavior.js
{"titleStateAndTextBadge":true,"failedAssetsRecover":true,"failedRenderRecovers":true,"staleRetryIsInert":true,"checkoutFetchIsAutomatic":true,"displayedComparisonRepair":true,"bridgeAfterPaint":true,"bridgeFramesOwned":true,"hiddenReadiness":true,"markdownOwnership":true,"checkRows":true,"headerAges":true,"headerShape":true,"widestNotes":{"Fetched just now via GitHub CLI":"Fetched 59 min ago via GitHub CLI","Fetched 3 h ago via GitHub CLI":"Fetched 59 min ago via GitHub CLI","Offline · fetched 12 d ago via GitHub CLI":"Offline · fetched 59 min ago via GitHub CLI","Description fetched 7 min ago via GitHub CLI":"Description fetched 59 min ago via GitHub CLI","Fetched at an unknown time via GitHub CLI":"Fetched at an unknown time via GitHub CLI"},"holdLifts":{"today":"2:05 PM","tomorrow":"9/18/26, 12:30 AM","next year":"1/2/27, 8:00 AM"},"headerSummary":["Conversation, the comparison not yet read: the pending placeholder","the comparison read: the summary","Changes: the summary","Checks, the comparison not yet read: the pending placeholder","Checks, the comparison read: the summary","the same pull request again in this document, before any idle: the summary","opened on Changes, from what its diff read: the summary","opened again on Conversation after Changes, before any idle: the summary","a read that will fail, not yet answered: the pending placeholder","the read fails: nothing","a repaint after it failed, its read asked again: the pending placeholder","that read fails too: nothing","a comparison the summary draws nothing for: nothing","opened on Changes, whose diff reads no comparison: nothing","the record on its way: the pending placeholder","a direct link's page before its first answer: the pending placeholder","its first answer: not cached, its own fetch to be sent: the pending placeholder","its fetch's core preview: the pending placeholder","its record lands, the comparison not yet read: the pending placeholder","the comparison read: the summary","a direct link's first answer: not GitHub's: nothing","a direct link's first answer: a server with no store, its own fetch to be sent: nothing","a direct link's first answer: its refresh failed, nothing running: nothing","a direct link's first answer: a core, its refresh failed, nothing running: nothing","a record that names no comparison: nothing","a core preview whose read prepares its comparison: the pending placeholder","its record lands, the comparison not yet read: the pending placeholder","the comparison read: the summary","a core preview whose read prepares no comparison: nothing","a prepared core, the page's own fetch still to be sent: the pending placeholder","a core whose read ended, the page's own fetch still to be sent: the pending placeholder","a record whose comparison the page asked to prepare: the pending placeholder","the preparation ends with no comparison: nothing","a record whose comparison nothing prepares: nothing","Changes, its diff reads no comparison: nothing","a record with a moved head is followed: its diff reads the comparison: the summary","the reader goes back: the earlier diff reads none again: the summary","the reader takes the newer changes, their diff not yet read: the summary","their diff reads the comparison: the summary","Changes, its diff throws: nothing","Retry, the diff not yet read: the pending placeholder","the diff reads the comparison: the summary","Changes, its diff still reading: the pending placeholder","the record then names no comparison: nothing"],"summaryBrief":["a direct link's page before its first answer, its head unknown: the pending placeholder; 1 reads","its core preview, of the list's head and base branch: the brief line \"1 A, 2 M · +12 −4\"; 1 reads","its record lands, the comparison not yet read: the brief line \"1 A, 2 M · +12 −4\"; 1 reads","the comparison read: the summary; 1 reads","a direct link's page, the list of an older head: the pending placeholder; 1 reads","its core preview, of a newer head: the pending placeholder; 1 reads","a record whose list was read for another base branch: the pending placeholder; 1 reads","a core preview, the local comparison's list, whose base the core cannot say: the pending placeholder; 1 reads","its record lands, naming the same comparison: the brief line \"1 A, 2 M · +12 −4\"; 1 reads","a record whose comparison has another base than the local list's: the pending placeholder; 1 reads","a record of the list's head, its comparison not yet read: the brief line \"1 A, 2 M · +12 −4\"; 1 reads","the comparison's read fails: the brief line \"1 A, 2 M · +12 −4\"; 1 reads","no list cached: the pending placeholder; 1 reads","a record of a list that only adds lines: the brief line \"1 A, 2 M · +3,893\"; 1 reads","opened from a Pulls row that drew its line: the brief line \"1 M · +12 −4\"; 0 reads","opened from a Pulls row whose line the lane marked out of date, read again: the brief line \"1 A, 2 M · +12 −4\"; 1 reads","a page that went before its read answered, its summary drawn: the summary; 1 reads"],"coldHold":["mounted with no record in hand: header github-pull-cold, tab column github-pull-cold","its record lands, the conversation waiting for its Markdown: header shown, tab column shown","the conversation's first paint, at its bound: header shown, tab column shown","on Changes, mounted with no record in hand: header github-pull-cold, tab column github-pull-cold","its record lands: header shown, tab column shown","mounted with its record in hand: header shown, tab column shown","no Pulls row in hand, mounted with no record in hand: title \"Pull request #7\", plain","its Pulls row in hand, mounted with no record in hand: title \"Count to two in the app #7\", the record's shape","its Pulls row in hand, mounted with no record in hand: header github-pull-cold, tab column github-pull-cold","two repositories' rows for its number, mounted with no record in hand: title \"Pull request #7\", plain"],"counterpart":["mounted with no record in hand: the corner after the title \"Pull request #7\"; asked /pull/7","its record lands: the corner after the title \"Count to two in the app\", the same corner; asked /pull/7","a poll brings a new title: the corner after the title \"Count to three in the app\", the same corner; asked /pull/7","the route shows Checks: the corner after the title \"Count to three in the app\", the same corner; asked /pull/7/checks","an SDK with no button: the corner after the title \"Count to two in the app\"; asked for none"],"tabKeys":["before the record, the tab column in the page: Conversation C, Docs D, Changes G, Checks E; live conversation docs files checks","C: showed Conversation","G: opened the files route","the record arrives and paintHeader keeps the column: Conversation C, Docs D, Changes G, Checks E","live: conversation docs files checks","numbered: 1 Browse code","1: POST /api/source/pin {\"oid\":\"85fcb2fa9e77eb5db485ffef445cbbc645d6db4a\",\"under\":\"refs/pull/7/head\",\"view\":\"/view/\"}","C: showed Conversation","G: opened the files route","the route arrives: Changes","numbered on Changes: 1 Browse code","the navigation's Refresh, the page offering one: POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"recovery\":{\"base\":\"f92fd713acd521d4ebb62fb9f345ec927b8b6d1b\",\"head\":\"85fcb2fa9e77eb5db485ffef445cbbc645d6db4a\"}}","numbered after a refresh serves the head: 1 Browse code","1: navigation.open /view/","the navigation's Refresh, the page offering one: POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"recovery\":{\"base\":\"f92fd713acd521d4ebb62fb9f345ec927b8b6d1b\",\"head\":\"85fcb2fa9e77eb5db485ffef445cbbc645d6db4a\"}}","numbered after a refresh with no pin: none","1: not handled","the navigation's Refresh, the page offering one: POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"recovery\":{\"base\":\"f92fd713acd521d4ebb62fb9f345ec927b8b6d1b\",\"head\":\"85fcb2fa9e77eb5db485ffef445cbbc645d6db4a\"}}","numbered with the code on the head: 1 Browse code","the navigation's Refresh, the page offering one: POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"recovery\":{\"base\":\"f92fd713acd521d4ebb62fb9f345ec927b8b6d1b\",\"head\":\"85fcb2fa9e77eb5db485ffef445cbbc645d6db4a\"}}","while that refresh runs, the page can refresh: false","the navigation's Refresh, the page not offering one: nothing asked","once the refresh ends, the page can refresh: true","on Conversation once the refresh ends, the page can refresh: false","numbered on Conversation once the refresh ends: 1 Browse code","2: not handled","Shift+H: not handled","Shift+E: opened the checks route","Shift+C: opened the conversation route","Ctrl+G: not handled","staged inert: G: not handled","committed: G: opened the files route","disposed: Conversation none, Docs none, Changes none, Checks none; keys none; G: not handled","a failed first read takes the column out: live none","G: not handled","on Changes, Shift held while it is out: badges none","the next read answers, and the returning tabs are badged: Conversation C, Docs D, Changes G, Checks E","the next read answers and paintHeader puts the column back: Conversation C, Docs D, Changes G, Checks E","live: conversation docs files checks","G: showed Changes","no block in the description: Conversation C, Docs D, Changes G, Checks E; live conversation docs files checks","R: not handled","a block in the description: Guided Review R, Conversation C, Docs D, Changes G, Checks E; live conversation docs files guided checks","R: showed Guided Review","the route arrives: Guided Review","the block leaves while its tab is shown: Guided Review R, Conversation C, Docs D, Changes G, Checks E; Guided Review","back on Conversation: Conversation C, Docs D, Changes G, Checks E; R: not handled","the block returns while Shift is held: badges Guided Review R, Conversation C, Docs D, Changes G, Checks E","R: showed Guided Review","an example of the block inside another fence: Guided Review R, Conversation C, Docs D, Changes G, Checks E","the guide, with no diff plugin or allowlist here, said: metabrowser github: the diff plugin did not load for the guide; metabrowser github: the guide's notes will show as typed","disposed: keys none"],"guideIntroduction":["asked: pull-files-summary, stacks, guided-review, pull-markdown, pull","the guide answered, its description's Markdown not yet: the notice hidden; the description hidden; a step waits out of sight true","the Markdown is inserted: the notice says This pull request has no guide.; the description shows Counts to two, rendered.; a step waits out of sight false","warned: 2"],"guideIntroductionBound":["asked: pull-files-summary, stacks, guided-review, pull-markdown, pull","the guide answered, its description's Markdown not yet: the notice hidden; the description hidden; a step waits out of sight true","its Markdown never comes, and the bound runs out: the notice says This pull request has no guide.; the description shows its placeholder; a step waits out of sight false","warned: 2"],"textRefusal":["refused past the deadline: plain, 1 notice right after it, a status: This text took too long to render, so it is shown as written.","rebuilt for another state, its Markdown not yet answered: plain, 1 notice right after it, a status: This text took too long to render, so it is shown as written., new element","a newer record, the same text refused again as unavailable: plain, 1 notice right after it, a status: This text could not be rendered, so it is shown as written. Reload the page to try again., new element","a newer record whose Markdown renders: rendered rendered A, no notice, same element"],"textDiagrams":["a description and a comment with no Mermaid block: 0 blocks, 0 in a figure; asked nothing; bindings none","the same with Mermaid blocks, on a folder's page: 2 blocks, 2 in a figure; asked markdown plugin, markdown plugin, kpress-diagrams, kpress-diagram-controls, kpress-diagrams, kpress-diagram-controls, the mermaid bundle's address; bindings body as image, 1 figure, Mermaid the diagram frame's; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's","a description and a comment each with a Mermaid block: 2 blocks, 2 in a figure; asked markdown plugin, markdown plugin, kpress-diagrams, kpress-diagram-controls, kpress-diagrams, kpress-diagram-controls, the mermaid bundle's address; bindings body as image, 1 figure, Mermaid the diagram frame's, disposed; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's, disposed; body as image, 1 figure, Mermaid the diagram frame's; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's","a poll of the same record: 2 blocks, 2 in a figure; asked nothing; bindings body as image, 1 figure, Mermaid the diagram frame's, disposed; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's, disposed; body as image, 1 figure, Mermaid the diagram frame's; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's","Changes and back to Conversation: 2 blocks, 2 in a figure; asked nothing; bindings body as image, 1 figure, Mermaid the diagram frame's, disposed; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's, disposed; body as image, 1 figure, Mermaid the diagram frame's; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's","the description edited, the comment not: 2 blocks, 2 in a figure; asked markdown plugin, kpress-diagrams, kpress-diagram-controls, the mermaid bundle's address; bindings body as image, 1 figure, Mermaid the diagram frame's, disposed; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's, disposed; body as image, 1 figure, Mermaid the diagram frame's, disposed; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's; body as image, 1 figure, Mermaid the diagram frame's","the description's block taken out: 1 block, 1 in a figure; asked nothing; bindings body as image, 1 figure, Mermaid the diagram frame's, disposed; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's, disposed; body as image, 1 figure, Mermaid the diagram frame's, disposed; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's; body as image, 1 figure, Mermaid the diagram frame's, disposed","a block whose text is replaced before the Markdown plugin arrives: 1 block, 1 in a figure; asked markdown plugin; bindings body as image, 1 figure, Mermaid the diagram frame's, disposed; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's, disposed; body as image, 1 figure, Mermaid the diagram frame's, disposed; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's; body as image, 1 figure, Mermaid the diagram frame's, disposed","the page ends: 1 block, 1 in a figure; asked nothing; bindings body as image, 1 figure, Mermaid the diagram frame's, disposed; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's, disposed; body as image, 1 figure, Mermaid the diagram frame's, disposed; issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's, disposed; body as image, 1 figure, Mermaid the diagram frame's, disposed"],"switchUnavailable":["the diff plugin's assets not loading: The switch request failed.; asked nothing","the switch module not loading: The switch request failed.; asked nothing"],"eventLogDetails":["mounted, the comparison not yet read: the pending placeholder; githubPull:diffSummary {\"number\":7} timed from its start running","still waiting at the late threshold: the late line \"The summary of changes has not arrived after 10 s. Details\"; githubPull:diffSummary {\"number\":7} timed from its start running","Details asked for {\"client\":\"k3v9q2zx\"}, abortable true","Details opened: expanded true; the panel says \"Still running: checkout._pull_job for 61.0 s\"","Details closed: expanded false; panel in the header false","Details asked for {\"client\":\"k3v9q2zx\"}, abortable true","the page left: panel in the header false; expanded false; githubPull:diffSummary {\"number\":7} timed from its start ended never_completed","another page, late: the late line \"The summary of changes has not arrived after 10 s. Details\"; githubPull:diffSummary {\"number\":7} timed from its start running","Details asked for {\"client\":\"k3v9q2zx\"}, abortable true","its comparison read, its Details open: the summary; githubPull:diffSummary {\"number\":7} timed from its start ended ok","the late line's Details: expanded false; panel in the header false","a page whose comparison is read at once: the summary; githubPull:diffSummary {\"number\":7} timed from its start ended ok","a failed refresh, ended 2026-09-17T12:30:00Z: \"Could not reach GitHub.Details\"","Details asked for {\"client\":\"k3v9q2zx\",\"since\":\"2026-09-17T11:30:00Z\",\"until\":\"2026-09-17T12:31:00Z\"}, abortable true","no reporter: \"The event log is not available here.\""],"statusRemedies":["a current record whose last refresh failed: status \"Could not reach GitHub.DetailsRetry\"; remedy Retry; note shown; asked nothing; Refresh may refresh it","Retry pressed, its refresh not yet started: status \"Could not reach GitHub.DetailsRetry\"; remedy Retry (waiting); note shown; asked POST /api/plugin/github/pull-refresh {\"number\":8,\"retry\":true}; Refresh has nothing to refresh","Retry pressed again while it waits: status \"Could not reach GitHub.DetailsRetry\"; remedy Retry (waiting); note shown; asked nothing; Refresh has nothing to refresh","the refresh runs: status none; remedy none; note shown; asked nothing; Refresh has nothing to refresh","a direct link to a pull request whose fetch failed: status \"This pull request has not been fetched yet.Could not reach GitHub.DetailsFetch\"; remedy Fetch; note none; asked nothing; Refresh may refresh it","Fetch pressed: status \"Fetching the pull request…Could not reach GitHub.Details\"; remedy none; note none; asked POST /api/plugin/github/pull-refresh {\"number\":7,\"retry\":true,\"wait_core\":true}; Refresh has nothing to refresh","a direct link to a copy saved by another version: status \"The saved copy of this pull request is from another version.Fetch\"; remedy Fetch; note none; asked nothing; Refresh may refresh it"]}
? 0
```

The selected and direct cold-page cases hold the POST until a description preview is
ready.
It verifies that the preview’s description is asked for once and rendered from the
core, explicit unfinished sections, no premature comparison actions, full-record
priority, and cancellation without losing the previous useful surface.
Checks has its own route and loading state, and it retains the existing check links and
notices once the record is ready.

```console
$ node tests/dom/github-pull-core-preview-behavior.js
{"description":"rendered preview before full conversation","pendingParts":["discussion","checks"],"checkResults":{"route":"/pull/7/checks","links":2,"empty":true,"pending":true},"waitCorePost":{"number":7,"retry":true,"wait_core":true},"previewMarkdownRequests":1,"fullMarkdownRequests":1,"fullRecordWins":true,"crossOwnerRetirement":true,"stagedReplacement":"A retained through B cancellation until C commits"}
? 0
```

A record cached before label colors names its labels alone.
On the first read that shows one the envelope has no entry for, the page asks for the
repository’s label set at once, and the job that starts makes its next read a fast poll.
It keeps polling fast while the envelope says the job runs.
Once the set is cached, the label it holds takes its color and tooltip, a label GitHub
no longer has stays neutral, and nothing else the page paints changes.
A page whose set is already being read asks for nothing.
One the server finds not due asks once and stays on its slow poll, and labels with their
own colors never ask.

```console
$ node tests/dom/github-pull-labels-behavior.js
{"labelsPending":[{"step":"a first read of labels named alone","requests":["GET /api/plugin/github/pull?number=7","POST /api/plugin/github/labels-refresh {}"],"poll":"fast","labels":["enhancement neutral no tip","deleted-on-github neutral no tip"]},{"step":"the set's job runs","requests":["GET /api/plugin/github/pull?number=7 (If-None-Match)"],"poll":"fast","labels":"unchanged"},{"step":"the set is cached","requests":["GET /api/plugin/github/pull?number=7 (If-None-Match)"],"poll":"slow","labels":["enhancement #2700af tip","deleted-on-github neutral no tip"]},{"step":"nothing changes","requests":["GET /api/plugin/github/pull?number=7 (If-None-Match)"],"poll":"slow","labels":"unchanged"},{"step":"a first read while the job runs","requests":["GET /api/plugin/github/pull?number=7"],"poll":"fast","labels":["enhancement neutral no tip","deleted-on-github neutral no tip"]},{"step":"a label the set does not hold","requests":["GET /api/plugin/github/pull?number=7","POST /api/plugin/github/labels-refresh {}"],"poll":"slow","labels":["enhancement #2700af tip","deleted-on-github neutral no tip"]},{"step":"the next poll","requests":["GET /api/plugin/github/pull?number=7 (If-None-Match)"],"poll":"slow","labels":"unchanged"},{"step":"labels with their own colors","requests":["GET /api/plugin/github/pull?number=7"],"poll":"slow","labels":["enhancement #2700af tip"]}]}
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
Every review’s heading is its author, “reviewed”, and its age, with a chip after the age
only for a state the verb does not say: Approved, Changes requested, and Dismissed, and
a state GitHub adds later as itself, even one named as an `Object.prototype` property
is. A plain review and a pending one have no chip (`reviewHeadings`).

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
  "keptCommitRowsRetellAges": true,
  "reviewHeadings": {
    "review/9007199254740993": "maintainer reviewed 1d ago",
    "review/16": "maintainer reviewed 1d ago [Changes requested]",
    "review/17": "maintainer reviewed 1d ago [Dismissed]",
    "review/18": "maintainer reviewed 1d ago [Escalated]",
    "review/19": "maintainer reviewed 1d ago [Constructor]",
    "review/3279967139": "maintainer reviewed 1d ago [Approved]",
    "review/15": "maintainer reviewed (pending)"
  }
}
? 0
```
