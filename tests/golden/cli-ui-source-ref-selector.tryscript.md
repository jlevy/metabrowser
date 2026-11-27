---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Source Ref Selector

A page on a served mirror’s pin shows a compact button naming the ref it was rendered
for.
Opening it lists every one of the mirror’s branches or tags from `/api/source/refs`,
with the served ref marked.
Primary and default branches precede other branches.
Each group and the tag list sort newest first.
The filter box asks again after a pause in typing.
A newer filter or closing the list aborts a request still on its way.
Choosing a ref switches the served pin with `POST /api/source/pin`, naming the page’s
`/view/` address so the answer says where the page goes: the same file when the new
revision has it, else the root.

This browserless session loads the production `static/source-ref-selector.js` and plays
the server’s side from `tests/fixtures/source-ref-selector-responses.json`: what the
in-process application answered for a real mirror’s listings and switches.
`tests/test_source_ref_selector_session.py` replays them and fails when the recording
drifts. Timers and paint are injected, and each request waits for the step to answer it;
each step records the requests the selector made, whether a filter pause is pending,
what it would paint, and where it navigated.
`labels` is what the button says for a page on a tag, a pull request’s head, with its
number set bold in brackets, and a commit with no ref; `keys` is where an arrow, Home,
or End key moves focus in a list of three rows, `-1` being the filter box and `null` a
key the list leaves alone.
`windows` is which rows a list draws (`rowWindow`): those in its view and `overscan`
more on either side, at the top, the middle, and the end of 10,001 rows, so the page
draws about as many rows for every ref as for a few; before a row is measured, the first
rows. The row that takes Tab is drawn too wherever the list is scrolled, since focus may
be on it and Tab from the filter box goes to it.

A served checkout’s conversation is a session of its own, below: one transcript of both
is more than a golden can match.

```console
$ node tests/dom/source-ref-selector-session.js
{
  "steps": [
    {
      "step": "the button names the served branch",
      "requests": [],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": false
      }
    },
    {
      "step": "opening asks for the branches",
      "requests": [
        "GET /api/source/refs?kind=branch"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "branch",
        "query": "",
        "loading": true,
        "switching": false,
        "rows": [],
        "note": "Loading branches…",
        "error": null
      }
    },
    {
      "step": "opening lists the branches",
      "requests": [],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "branch",
        "query": "",
        "loading": false,
        "switching": false,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current]",
          "feature c7ae2a3 2026-01-01T02:00:00Z"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "typing waits for a pause",
      "requests": [],
      "filterPending": true,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "branch",
        "query": "",
        "loading": false,
        "switching": false,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current]",
          "feature c7ae2a3 2026-01-01T02:00:00Z"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "the pause asks once",
      "requests": [
        "GET /api/source/refs?kind=branch&q=feat"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "branch",
        "query": "feat",
        "loading": false,
        "switching": false,
        "rows": [
          "feature c7ae2a3 2026-01-01T02:00:00Z"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "a newer filter aborts the older request",
      "requests": [
        "GET /api/source/refs?kind=branch&q=zzz",
        "aborted GET /api/source/refs?kind=branch&q=zzz",
        "GET /api/source/refs?kind=branch&q=feat"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "branch",
        "query": "feat",
        "loading": false,
        "switching": false,
        "rows": [
          "feature c7ae2a3 2026-01-01T02:00:00Z"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "a filter that matches nothing says so",
      "requests": [
        "GET /api/source/refs?kind=branch&q=zzz"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "branch",
        "query": "zzz",
        "loading": false,
        "switching": false,
        "rows": [],
        "note": "No branches match.",
        "error": null
      }
    },
    {
      "step": "tags list newest first",
      "requests": [
        "GET /api/source/refs?kind=branch",
        "GET /api/source/refs?kind=tag"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "tag",
        "query": "",
        "loading": false,
        "switching": false,
        "rows": [
          "v1 fcb9d63 2026-01-01T00:00:00Z"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "a refused listing says so",
      "requests": [
        "GET /api/source/refs?kind=tag"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "tag",
        "query": "",
        "loading": false,
        "switching": false,
        "rows": [],
        "note": "",
        "error": "The tags could not be listed. Try again."
      }
    },
    {
      "step": "closing",
      "requests": [],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": false
      }
    },
    {
      "step": "closing aborts the request on its way",
      "requests": [
        "GET /api/source/refs?kind=branch",
        "aborted GET /api/source/refs?kind=branch"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": false
      }
    },
    {
      "step": "a switch is under way",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/feature\",\"view\":\"/view/g1-Tk9URVMubWQ\"}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "branch",
        "query": "",
        "loading": false,
        "switching": true,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current]",
          "feature c7ae2a3 2026-01-01T02:00:00Z"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "a branch without the page's file opens at the root",
      "requests": [],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "branch",
        "query": "",
        "loading": false,
        "switching": true,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current]",
          "feature c7ae2a3 2026-01-01T02:00:00Z"
        ],
        "note": "",
        "error": null
      },
      "navigated": [
        "/view/"
      ]
    },
    {
      "step": "the button names the branch after the switch",
      "requests": [],
      "filterPending": false,
      "paint": {
        "button": "Branch: feature",
        "open": false
      }
    },
    {
      "step": "a branch with the page's file keeps it",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/topic\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: feature",
        "open": false
      },
      "navigated": [
        "/view/g1-UkVBRE1FLm1k"
      ]
    },
    {
      "step": "choosing what the page shows only closes",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/topic\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": false
      }
    },
    {
      "step": "a ref gone from the mirror says so",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/gone\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "branch",
        "query": "",
        "loading": false,
        "switching": false,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current]",
          "feature c7ae2a3 2026-01-01T02:00:00Z"
        ],
        "note": "",
        "error": "That branch or tag is no longer in the mirror."
      }
    },
    {
      "step": "a page off /view/ names no address and opens at the root",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/feature\"}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": false
      },
      "navigated": [
        "/view/"
      ]
    }
  ],
  "labels": [
    "Tag: v1",
    "Pull request: #7 [bold #7]",
    "Commit: 42382ea"
  ],
  "copies": [
    {
      "name": "topic",
      "label": "topic",
      "ref": "refs/remotes/origin/topic",
      "kind": "remote"
    },
    {
      "name": "v1",
      "label": "v1",
      "ref": "refs/tags/v1",
      "kind": "tag"
    },
    {
      "name": "feature/long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-←<literal>",
      "label": "feature/long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-←<literal>",
      "ref": "refs/remotes/origin/feature/long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-long-←<literal>",
      "kind": "remote"
    }
  ],
  "keys": [
    "ArrowDown from -1: 0",
    "ArrowUp from -1: null",
    "Home from -1: null",
    "ArrowDown from 0: 1",
    "ArrowDown from 2: 2",
    "ArrowUp from 0: -1",
    "ArrowUp from 2: 1",
    "Home from 2: 0",
    "End from 0: 2",
    "Enter from 1: null",
    "ArrowDown from -1 in an empty list: null"
  ],
  "overscan": 20,
  "windows": [
    "10001 rows 28 px tall, scrolled 0 px in 320 px, Tab on row 0: rows 0 to 32",
    "10001 rows 28 px tall, scrolled 0 px in 320 px, Tab on row 9000: rows 0 to 32 and row 9000",
    "10001 rows 28 px tall, scrolled 140010 px in 320 px, Tab on row 0: rows 4980 to 5032 and row 0",
    "10001 rows 28 px tall, scrolled 140010 px in 320 px, Tab on row 5003: rows 4980 to 5032",
    "10001 rows 28 px tall, scrolled 279708 px in 320 px, Tab on row 10000: rows 9969 to 10001",
    "3 rows 28 px tall, scrolled 0 px in 320 px, Tab on row 1: rows 0 to 3",
    "10001 rows 0 px tall, scrolled 0 px in 0 px, Tab on row 0: rows 0 to 40",
    "0 rows 28 px tall, scrolled 0 px in 320 px, Tab on row 0: rows 0 to 0",
    "10001 rows 28 px tall (every 4th 46 px), scrolled 0 px in 320 px, Tab on row 0: rows 0 to 30",
    "10001 rows 28 px tall (every 4th 46 px), scrolled 115264 px in 320 px, Tab on row 0: rows 3526 to 3577 and row 0",
    "10001 rows 28 px tall (every 4th 46 px), scrolled 324726 px in 320 px, Tab on row 10000: rows 9971 to 10001",
    "10001 rows 28 px tall (every 10,001st 46 px), scrolled 0 px in 320 px, Tab on row 0: rows 0 to 31"
  ]
}
? 0
```

## A Served Checkout

The same module is a served checkout’s selector: a folder that is a repository’s root.
`tests/dom/source-ref-selector-checkout-session.js` plays it, on what the application
answered for the checkout `tests/source_checkout_fixture.py` builds, recorded in
`tests/fixtures/source-ref-selector-checkout-responses.json`.

Its tabs begin with **Working tree**, which is what a folder opens on and the one choice
that is not a ref, and it has a list more, the remote-tracking branches.
A list opens on the tab that holds what the page shows (`opens`): the working tree’s on
a page of the files on disk, where its one entry is current, and a ref’s own list on a
page of that ref. The working tree’s tab asks for no refs (`kind=working_tree`), and its
entry names the branch `HEAD` is on, or the commit a detached one is at, and the
folder’s path.

A branch is shown as a pinned revision, at the revision’s address for the page’s file.
The checked-out branch is badged and is a ref like any other, so choosing it shows its
commit. A press on the Working tree tab from a page that shows a ref (`pressKind`) asks
the pin route for the working tree, as choosing the tab’s entry does; an arrow key onto
the tab (`setKind`) only shows its entry, and a press while the working tree is already
shown has nothing to switch.
The button names what the page shows in one form: “Working tree” and the branch the
files on disk are on, or a ref alone, so the checked-out branch’s own revision never
reads as its working tree (mb-cxpq), and the row is its label and the chooser’s button
in every state.

A `HEAD` that moves outside the page, in a terminal or an agent’s, is named in place:
`headChanged`, which the page’s watch on the checkout’s `HEAD` calls, asks where it is,
and the row, its tooltip (`tip`), the open tab’s entry, and an open Branches list’s
“checked out” mark follow, with no navigation.
`renders` counts the paints, so an answer that says the same is seen to draw nothing.

The same selector heads the Commits tab, which shows the revision chosen: a switch made
there names no address, and the page reloads on Commits at the tab’s own landing, the
`/view/` history entry whose state is `gitLanding`, where its row names the revision.
A switch that fails says why in the list.
A page left behind by a switch elsewhere offers a reload, which a mirror’s freshness row
does for a mirror. A checkout’s rows say which chip each name is drawn as, and its
`labels` are the button on the working tree on a branch, at a detached `HEAD`, and with
a `HEAD` the server could not read, then on a branch, a remote-tracking branch, a tag,
and a commit, each with its tooltip, which only the working tree’s words have.
A folder holding a `.git` that Git does not take for a repository’s root loses its row
when the listing says so, and a Git older than the one a checkout’s revisions are read
with is refused in the server’s own words.
`guard` is what each kind of page names on its data requests
(`static/source-pin-guard.js`), which is how a tab left behind is refused: a revision
its commit, a checkout’s working tree the word `working-tree`, and a plain folder
nothing, since its server can serve nothing else.
`folders` is where the working tree’s entry cuts a folder’s path to keep the folder’s
own name whole: at the name the server sends, whichever separator the path was joined
with, and nowhere when the folder is the home directory, whose path is `~`. `hold` is
what the page’s own data requests do while it switches: the server may serve the other
subject before the page has gone, so each waits for the answer and is held while the
page goes. The guard sends them when the switch is refused or changes nothing, when the
selector is taken away, when the back/forward cache shows the page again, and at the
hold’s bound, which runs from the ask; an earlier switch’s bound does not end a later
hold, and a request given up while it is held settles at once and is not sent.

```console
$ node tests/dom/source-ref-selector-checkout-session.js
{
  "checkout": {
    "steps": [
      {
        "step": "the button names the working tree and the branch it is on",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": false
        }
      },
      {
        "step": "opening asks where the working tree is, and for no refs",
        "requests": [
          "GET /api/source/refs?kind=working_tree"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "working_tree",
          "query": "",
          "loading": true,
          "switching": false,
          "rows": [],
          "note": "",
          "error": null
        }
      },
      {
        "step": "the list opens on the working tree's tab, its one entry current",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "working_tree",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [],
          "note": "",
          "error": null
        }
      },
      {
        "step": "the checkout's branches, with the checked-out branch marked",
        "requests": [
          "GET /api/source/refs?kind=branch"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [
            "topic 42382ea 2026-01-01T01:00:00Z [checked out] (local chip)",
            "local-work 25e0a2a 2026-02-01T00:00:00Z (local chip)",
            "feature c7ae2a3 2026-01-01T02:00:00Z (local chip)"
          ],
          "note": "",
          "error": null
        }
      },
      {
        "step": "a checkout has a list more, its remote-tracking branches",
        "requests": [
          "GET /api/source/refs?kind=remote"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "remote",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [
            "origin/topic 42382ea 2026-01-01T01:00:00Z (remote chip)",
            "origin/feature c7ae2a3 2026-01-01T02:00:00Z (remote chip)"
          ],
          "note": "",
          "error": null
        }
      },
      {
        "step": "tags",
        "requests": [
          "GET /api/source/refs?kind=tag"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "tag",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [
            "local-tag c7ae2a3 2026-01-01T02:00:00Z (tag chip)",
            "v1 fcb9d63 2026-01-01T00:00:00Z (tag chip)"
          ],
          "note": "",
          "error": null
        }
      },
      {
        "step": "a press on Working tree while it is shown only shows its tab",
        "requests": [
          "GET /api/source/refs?kind=working_tree"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "working_tree",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [],
          "note": "",
          "error": null
        }
      },
      {
        "step": "a branch is asked for by its ref, with the folder's address",
        "requests": [
          "POST /api/source/pin {\"ref\":\"refs/heads/feature\",\"view\":\"/view/README.md\"}"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": true,
          "rows": [
            "topic 42382ea 2026-01-01T01:00:00Z [checked out] (local chip)",
            "local-work 25e0a2a 2026-02-01T00:00:00Z (local chip)",
            "feature c7ae2a3 2026-01-01T02:00:00Z (local chip)"
          ],
          "note": "",
          "error": null
        }
      },
      {
        "step": "the page goes to the same file in the revision",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": true,
          "rows": [
            "topic 42382ea 2026-01-01T01:00:00Z [checked out] (local chip)",
            "local-work 25e0a2a 2026-02-01T00:00:00Z (local chip)",
            "feature c7ae2a3 2026-01-01T02:00:00Z (local chip)"
          ],
          "note": "",
          "error": null
        },
        "navigated": [
          "/view/g1-UkVBRE1FLm1k"
        ]
      },
      {
        "step": "the button names the branch shown, and nothing else",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Branch: feature",
          "open": false
        }
      },
      {
        "step": "the list opens on Branches, where the branch shown is current",
        "requests": [
          "GET /api/source/refs?kind=branch"
        ],
        "filterPending": false,
        "paint": {
          "button": "Branch: feature",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout)",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [
            "topic 42382ea 2026-01-01T01:00:00Z [checked out] (local chip)",
            "local-work 25e0a2a 2026-02-01T00:00:00Z (local chip)",
            "feature c7ae2a3 2026-01-01T02:00:00Z [current] (local chip)"
          ],
          "note": "",
          "error": null
        }
      },
      {
        "step": "an arrow key onto Working tree shows its entry and switches nothing",
        "requests": [
          "GET /api/source/refs?kind=working_tree"
        ],
        "filterPending": false,
        "paint": {
          "button": "Branch: feature",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout)",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "working_tree",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [],
          "note": "",
          "error": null
        }
      },
      {
        "step": "the checked-out branch opens its commit, not the working tree",
        "requests": [
          "POST /api/source/pin {\"ref\":\"refs/heads/topic\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
        ],
        "filterPending": false,
        "paint": {
          "button": "Branch: feature",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout)",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": true,
          "rows": [
            "topic 42382ea 2026-01-01T01:00:00Z [checked out] (local chip)",
            "local-work 25e0a2a 2026-02-01T00:00:00Z (local chip)",
            "feature c7ae2a3 2026-01-01T02:00:00Z [current] (local chip)"
          ],
          "note": "",
          "error": null
        },
        "navigated": [
          "/view/g1-UkVBRE1FLm1k"
        ]
      },
      {
        "step": "the checked-out branch's revision is not its working tree",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Branch: topic",
          "open": false
        }
      },
      {
        "step": "the checked-out branch is current in Branches once it is shown",
        "requests": [
          "GET /api/source/refs?kind=branch"
        ],
        "filterPending": false,
        "paint": {
          "button": "Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout)",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [
            "topic 42382ea 2026-01-01T01:00:00Z [checked out] [current] (local chip)",
            "local-work 25e0a2a 2026-02-01T00:00:00Z (local chip)",
            "feature c7ae2a3 2026-01-01T02:00:00Z (local chip)"
          ],
          "note": "",
          "error": null
        }
      },
      {
        "step": "a press on Working tree asks for the files on disk, not for a ref",
        "requests": [
          "POST /api/source/pin {\"working_tree\":true,\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
        ],
        "filterPending": false,
        "paint": {
          "button": "Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout)",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": true,
          "rows": [
            "topic 42382ea 2026-01-01T01:00:00Z [checked out] [current] (local chip)",
            "local-work 25e0a2a 2026-02-01T00:00:00Z (local chip)",
            "feature c7ae2a3 2026-01-01T02:00:00Z (local chip)"
          ],
          "note": "",
          "error": null
        }
      },
      {
        "step": "the page goes to the same file in the folder",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout)",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": true,
          "rows": [
            "topic 42382ea 2026-01-01T01:00:00Z [checked out] [current] (local chip)",
            "local-work 25e0a2a 2026-02-01T00:00:00Z (local chip)",
            "feature c7ae2a3 2026-01-01T02:00:00Z (local chip)"
          ],
          "note": "",
          "error": null
        },
        "navigated": [
          "/view/README.md"
        ]
      },
      {
        "step": "a switch on the Commits tab names no address",
        "requests": [
          "POST /api/source/pin {\"ref\":\"refs/heads/feature\"}"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": false
        }
      },
      {
        "step": "the page reloads on the Commits tab's own landing",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": false
        },
        "navigated": [
          "/view/ {\"gitLanding\":true}"
        ]
      },
      {
        "step": "the reloaded Commits tab's row names the revision chosen there",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Branch: feature",
          "open": false
        }
      },
      {
        "step": "a switch that failed says so in the list, which stays open",
        "requests": [
          "GET /api/source/refs?kind=branch",
          "POST /api/source/pin {\"working_tree\":true,\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
        ],
        "filterPending": false,
        "paint": {
          "button": "Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout)",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [
            "topic 42382ea 2026-01-01T01:00:00Z [checked out] [current] (local chip)",
            "local-work 25e0a2a 2026-02-01T00:00:00Z (local chip)",
            "feature c7ae2a3 2026-01-01T02:00:00Z (local chip)"
          ],
          "note": "",
          "error": "The switch request failed."
        }
      },
      {
        "step": "closing the list clears it",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Branch: topic",
          "open": false
        }
      },
      {
        "step": "a page drawn before a checkout in a terminal names the branch it was on",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": false
        },
        "tip": "The files on disk, live. The checkout is on topic.",
        "renders": 1
      },
      {
        "step": "a HEAD that moved asks where it is, and for no refs, with the list closed",
        "requests": [
          "GET /api/source/refs?kind=working_tree"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": false
        },
        "tip": "The files on disk, live. The checkout is on topic.",
        "renders": 1
      },
      {
        "step": "the row names the branch HEAD is on now, in place",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: feature",
          "open": false
        },
        "tip": "The files on disk, live. The checkout is on feature.",
        "renders": 2
      },
      {
        "step": "the open tab's entry names it too",
        "requests": [
          "GET /api/source/refs?kind=working_tree"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: feature",
          "open": true,
          "workingTree": "Working tree on feature: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "working_tree",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [],
          "note": "",
          "error": null
        },
        "tip": "The files on disk, live. The checkout is on feature.",
        "renders": 4
      },
      {
        "step": "an answer that says the same draws nothing",
        "requests": [
          "GET /api/source/refs?kind=working_tree"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: feature",
          "open": true,
          "workingTree": "Working tree on feature: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "working_tree",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [],
          "note": "",
          "error": null
        },
        "tip": "The files on disk, live. The checkout is on feature.",
        "renders": 4
      },
      {
        "step": "a HEAD detached since names its commit, in the row and the entry",
        "requests": [
          "GET /api/source/refs?kind=working_tree"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · 42382ea",
          "open": true,
          "workingTree": "Working tree at 42382ea: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "working_tree",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [],
          "note": "",
          "error": null
        },
        "tip": "The files on disk, live. HEAD is detached at 42382ea.",
        "renders": 5
      },
      {
        "step": "Branches as they were listed while HEAD was on feature",
        "requests": [
          "GET /api/source/refs?kind=branch"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: feature",
          "open": true,
          "workingTree": "Working tree on feature: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [
            "topic 42382ea 2026-01-01T01:00:00Z (local chip)",
            "local-work 25e0a2a 2026-02-01T00:00:00Z (local chip)",
            "feature c7ae2a3 2026-01-01T02:00:00Z [checked out] (local chip)"
          ],
          "note": "",
          "error": null
        },
        "tip": "The files on disk, live. The checkout is on feature.",
        "renders": 7
      },
      {
        "step": "the open Branches list follows: no branch is checked out",
        "requests": [
          "GET /api/source/refs?kind=branch"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · 42382ea",
          "open": true,
          "workingTree": "Working tree at 42382ea: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [
            "topic 42382ea 2026-01-01T01:00:00Z (local chip)",
            "local-work 25e0a2a 2026-02-01T00:00:00Z (local chip)",
            "feature c7ae2a3 2026-01-01T02:00:00Z (local chip)"
          ],
          "note": "",
          "error": null
        },
        "tip": "The files on disk, live. HEAD is detached at 42382ea.",
        "renders": 8
      },
      {
        "step": "a change heard during a load the reader waits on asks nothing yet",
        "requests": [
          "GET /api/source/refs?kind=tag"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · 42382ea",
          "open": true,
          "workingTree": "Working tree at 42382ea [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "tag",
          "query": "",
          "loading": true,
          "switching": false,
          "rows": [],
          "note": "Loading tags…",
          "error": null
        },
        "tip": "The files on disk, live. HEAD is detached at 42382ea.",
        "renders": 9
      },
      {
        "step": "and asks again once that load has answered",
        "requests": [
          "GET /api/source/refs?kind=tag"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "tag",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [
            "local-tag c7ae2a3 2026-01-01T02:00:00Z (tag chip)",
            "v1 fcb9d63 2026-01-01T00:00:00Z (tag chip)"
          ],
          "note": "",
          "error": null
        },
        "tip": "The files on disk, live. The checkout is on topic.",
        "renders": 10
      },
      {
        "step": "a refused ask leaves the row as it was",
        "requests": [
          "GET /api/source/refs?kind=working_tree"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": false
        },
        "tip": "The files on disk, live. The checkout is on topic.",
        "renders": 1
      },
      {
        "step": "choosing the working tree's entry while it is shown only closes",
        "requests": [
          "POST /api/source/pin {\"working_tree\":true,\"view\":\"/view/README.md\"}"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": false
        }
      },
      {
        "step": "a ref gone from the checkout says so, and nothing is fetched",
        "requests": [
          "POST /api/source/pin {\"ref\":\"refs/heads/gone\",\"view\":\"/view/README.md\"}"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "working_tree",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [],
          "note": "",
          "error": "That branch or tag is no longer in the checkout."
        }
      },
      {
        "step": "a working-tree page left behind offers a reload",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": false,
          "stale": "The server now shows another revision [Reload page]"
        }
      },
      {
        "step": "a revision's page left behind offers one too",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Branch: feature",
          "open": false,
          "stale": "The server now shows the working tree [Reload page]"
        }
      },
      {
        "step": "a folder Git does not take for a repository loses its row",
        "requests": [
          "GET /api/source/refs?kind=working_tree"
        ],
        "filterPending": false,
        "paint": {
          "removed": true
        }
      },
      {
        "step": "an older Git is refused, and the page says so",
        "requests": [
          "GET /api/source/refs?kind=working_tree",
          "GET /api/source/refs?kind=branch"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree · Branch: topic",
          "open": true,
          "workingTree": "Working tree on topic [current]",
          "lists": [
            "working_tree",
            "branch",
            "remote",
            "tag"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [],
          "note": "",
          "error": "Git on this machine is too old to list these. Update Git to see them."
        }
      },
      {
        "step": "a mirror's selector asks for no working tree and offers no reload",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Branch: topic",
          "open": false
        }
      }
    ],
    "labels": [
      "Working tree · Branch: topic (local chip) | The files on disk, live. The checkout is on topic.",
      "Working tree · c7ae2a3 (commit-ID face) | The files on disk, live. HEAD is detached at c7ae2a3.",
      "Working tree | The files on disk, live.",
      "Branch: feature (local chip) | null",
      "Remote branch: origin/feature (remote chip) | null",
      "Tag: v1 (tag chip) | null",
      "Commit: c7ae2a3 (commit-ID face) | null"
    ],
    "opens": {
      "a checkout's working tree": "working_tree",
      "a checkout's branch": "branch",
      "a checkout's remote-tracking branch": "remote",
      "a checkout's tag": "tag",
      "a checkout's commit with no ref": "branch",
      "a mirror's branch": "branch",
      "a mirror's tag": "tag",
      "a mirror's pull request": "branch"
    },
    "guard": {
      "a checkout's working tree": "working-tree; refused when another is served: true; while its own is: false",
      "a checkout's revision": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b; refused when another is served: true; while its own is: false",
      "a mirror's pin": "c7ae2a331f546e6a2431ed7093e9e430a9d1269b; refused when another is served: true; while its own is: false",
      "a plain folder": "nothing"
    },
    "folders": {
      "under the home directory": "~/src/[checkout]",
      "with the platform's other separator": "~\\src\\[checkout]",
      "the home directory itself": "[~]",
      "outside the home directory": "/srv/[checkout]"
    },
    "hold": [
      {
        "step": "a request made while the switch is asked waits for the answer",
        "sent": [],
        "bounds": [
          5000
        ]
      },
      {
        "step": "a page that goes holds its requests until it is gone",
        "sent": [],
        "bounds": [
          5000
        ]
      },
      {
        "step": "a page still there at the bound sends them, to be refused",
        "sent": [
          "/api/tree?depth=0 working-tree",
          "/api/tree?depth=0 working-tree"
        ],
        "bounds": []
      },
      {
        "step": "choosing what the page shows sends them when it is answered",
        "sent": [
          "/api/tree?depth=0 working-tree"
        ],
        "bounds": [
          5000
        ]
      },
      {
        "step": "a switch refused sends them when it is answered",
        "sent": [
          "/api/tree?depth=0 working-tree"
        ],
        "bounds": [
          5000
        ]
      },
      {
        "step": "a selector taken away during its switch sends them when it is answered",
        "sent": [
          "/api/tree?depth=0 working-tree"
        ],
        "bounds": [
          5000
        ]
      },
      {
        "step": "a request given up while it is held settles at once",
        "sent": [],
        "bounds": [
          5000
        ],
        "settled": "AbortError"
      },
      {
        "step": "and is not sent when the hold ends",
        "sent": [],
        "bounds": [
          5000
        ]
      },
      {
        "step": "a page the back/forward cache shows again sends them at once",
        "sent": [
          "/api/tree?depth=0 working-tree"
        ],
        "bounds": [
          5000
        ]
      },
      {
        "step": "the first switch's bound, firing during a second, sends nothing",
        "sent": [],
        "bounds": [
          5000
        ]
      },
      {
        "step": "and the second sends them when it is answered",
        "sent": [
          "/api/tree?depth=0 working-tree"
        ],
        "bounds": [
          5000
        ]
      },
      {
        "step": "a second source control cannot post while a ref switch is in flight",
        "sent": [
          "/api/source/pin null"
        ],
        "bounds": [],
        "refusal": "selection_busy"
      },
      {
        "step": "another source control can post after the first settles",
        "sent": [
          "/api/source/pin null"
        ],
        "bounds": []
      }
    ]
  }
}
? 0
```

## Open a Ref Menu Without Following Its Row

The production SDK renders literal labels separately from raw copy values and keeps its
copy buttons outside primary row links.
This session checks the same owned clipboard handler, keyboard reachability,
scroll/resize hiding and listener disposal.

```console
$ node tests/dom/sdk-copy-delegate-behavior.js
{
  "ref": {
    "name": "feature/←<literal>",
    "label": "fork:display",
    "kind": "local",
    "ref": "refs/heads/feature/←<literal>",
    "primary": "a",
    "nestedButtons": 0,
    "listenersAfterDispose": 0
  }
}
sdk copy delegate OK
? 0
```
