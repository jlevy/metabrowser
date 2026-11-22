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
the default branch first and then newest first, with the served ref marked; the filter
box asks again after a pause in typing, and a newer filter, or closing the list, aborts
a request still on its way.
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

`checkout` is the same module as a served checkout’s selector: a folder that is a
repository’s root, recorded in
`tests/fixtures/source-ref-selector-checkout-responses.json` from the checkout
`tests/source_checkout_fixture.py` builds.
Its panel begins with the working tree, which is what a folder opens on and the one
choice that is not a ref, and has a third list, the remote-tracking branches.
A branch is shown as a pinned revision, at the revision’s address for the page’s file.
The checked-out branch is badged and is a ref like any other, so choosing it shows its
commit; only the working-tree row asks the pin route for the working tree.
A page left behind by a switch elsewhere offers a reload, which a mirror’s freshness row
does for a mirror. A checkout’s rows say which chip each name is drawn as, and its
`labels` are the button on the working tree, a branch, a remote-tracking branch, a tag,
and a commit. A folder holding a `.git` that Git does not take for a repository’s root
loses its row when the listing says so, and a Git older than the one a checkout’s
revisions are read with is refused in the server’s own words.
`guard` is what each kind of page names on its data requests
(`static/source-pin-guard.js`), which is how a tab left behind is refused: a revision
its commit, a checkout’s working tree the word `working-tree`, and a plain folder
nothing, since its server can serve nothing else.
`folders` is where the Working tree row cuts a folder’s path to keep the folder’s own
name whole: at the name the server sends, whichever separator the path was joined with,
and nowhere when the folder is the home directory, whose path is `~`. `hold` is what the
page’s own data requests do while it switches: the server may serve the other subject
before the page has gone, so each waits for the answer and is held while the page goes.
The guard sends them when the switch is refused or changes nothing, when the selector is
taken away, when the back/forward cache shows the page again, and at the hold’s bound,
which runs from the ask; an earlier switch’s bound does not end a later hold, and a
request given up while it is held settles at once and is not sent.

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
        "error": "The tags could not be listed (HTTP 400)."
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
        "error": "That ref is no longer in the mirror."
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
  ],
  "checkout": {
    "steps": [
      {
        "step": "the button names the working tree",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Working tree",
          "open": false
        }
      },
      {
        "step": "the working tree is listed above the branches, and is what is served",
        "requests": [
          "GET /api/source/refs?kind=branch"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree",
          "open": true,
          "workingTree": "Working tree: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "branch",
            "tag",
            "remote"
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
        "step": "a checkout has a third list, its remote-tracking branches",
        "requests": [
          "GET /api/source/refs?kind=remote"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree",
          "open": true,
          "workingTree": "Working tree: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "branch",
            "tag",
            "remote"
          ],
          "kind": "remote",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [
            "origin/feature c7ae2a3 2026-01-01T02:00:00Z (remote chip)",
            "origin/topic 42382ea 2026-01-01T01:00:00Z (remote chip)"
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
          "button": "Working tree",
          "open": true,
          "workingTree": "Working tree: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "branch",
            "tag",
            "remote"
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
        "step": "a branch is asked for by its ref, with the folder's address",
        "requests": [
          "POST /api/source/pin {\"ref\":\"refs/heads/feature\",\"view\":\"/view/README.md\"}"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree",
          "open": true,
          "workingTree": "Working tree: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "branch",
            "tag",
            "remote"
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
          "button": "Working tree",
          "open": true,
          "workingTree": "Working tree: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "branch",
            "tag",
            "remote"
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
        "step": "the button names the branch shown",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Branch: feature",
          "open": false
        }
      },
      {
        "step": "the branch shown is current, and the working tree no longer is",
        "requests": [
          "GET /api/source/refs?kind=branch"
        ],
        "filterPending": false,
        "paint": {
          "button": "Branch: feature",
          "open": true,
          "workingTree": "Working tree: /sandbox/checkout (kept whole: checkout)",
          "lists": [
            "branch",
            "tag",
            "remote"
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
        "step": "the checked-out branch opens its commit, not the working tree",
        "requests": [
          "POST /api/source/pin {\"ref\":\"refs/heads/topic\",\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
        ],
        "filterPending": false,
        "paint": {
          "button": "Branch: feature",
          "open": true,
          "workingTree": "Working tree: /sandbox/checkout (kept whole: checkout)",
          "lists": [
            "branch",
            "tag",
            "remote"
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
        "step": "the working tree is asked for by name, not by a ref",
        "requests": [
          "POST /api/source/pin {\"working_tree\":true,\"view\":\"/view/g1-UkVBRE1FLm1k\"}"
        ],
        "filterPending": false,
        "paint": {
          "button": "Branch: topic",
          "open": false
        }
      },
      {
        "step": "the page goes to the same file in the folder",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Branch: topic",
          "open": false
        },
        "navigated": [
          "/view/README.md"
        ]
      },
      {
        "step": "choosing the working tree while it is shown only closes",
        "requests": [
          "POST /api/source/pin {\"working_tree\":true,\"view\":\"/view/README.md\"}"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree",
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
          "button": "Working tree",
          "open": true,
          "workingTree": "Working tree: /sandbox/checkout (kept whole: checkout) [current]",
          "lists": [
            "branch",
            "tag",
            "remote"
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
          "error": "That ref is no longer in the checkout."
        }
      },
      {
        "step": "a working-tree page left behind offers a reload",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Working tree",
          "open": false,
          "stale": "The server now shows another revision [Reload]"
        }
      },
      {
        "step": "a revision's page left behind offers one too",
        "requests": [],
        "filterPending": false,
        "paint": {
          "button": "Branch: feature",
          "open": false,
          "stale": "The server now shows the working tree [Reload]"
        }
      },
      {
        "step": "a folder Git does not take for a repository loses its row",
        "requests": [
          "GET /api/source/refs?kind=branch"
        ],
        "filterPending": false,
        "paint": {
          "removed": true
        }
      },
      {
        "step": "an older Git is refused in the server's words",
        "requests": [
          "GET /api/source/refs?kind=branch"
        ],
        "filterPending": false,
        "paint": {
          "button": "Working tree",
          "open": true,
          "workingTree": "Working tree [current]",
          "lists": [
            "branch",
            "tag",
            "remote"
          ],
          "kind": "branch",
          "query": "",
          "loading": false,
          "switching": false,
          "rows": [],
          "note": "",
          "error": "showing a branch or tag of a checkout needs Git 2.43.7 or newer, which is known never to fetch into it; this is git version 2.39.2"
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
      "Working tree",
      "Branch: feature (local chip)",
      "Remote branch: origin/feature (remote chip)",
      "Tag: v1 (tag chip)",
      "Commit: c7ae2a3"
    ],
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
