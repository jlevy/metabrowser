---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Source Ref Selector, a Checkout’s Origin

A folder that is a repository’s root lists its origin’s branches and tags from a store
Metabrowser keeps beside the checkout, as it last fetched them.
The checkout itself is never fetched into.

This browserless session loads the production `static/source-ref-selector.js` and
replays the answers a real checkout gave, recorded in
`tests/fixtures/source-ref-selector-origin-responses.json` by
`tests/test_source_ref_selector_origin_session.py`. The checkout’s own `origin/trunk` is
where its last fetch left it, and the origin has moved on.

- An open list makes a visible page’s own ask once, `{"for": "page"}`. The server
  fetches the store when it is older than its freshness window, and the list is asked
  for again while that fetch runs.
- The list of remote-tracking branches, and the list of tags, say the origin’s are as
  Metabrowser last fetched them, and when.
  The checkout’s own branches read no store.
- The navigation’s Refresh reads an open list again in place (`reread`), and one that
  says the same is not drawn again (`drawnAgain`). On the working tree’s page it also
  asks for the origin’s fetch as the reader’s own (`fetchOrigin`), whatever the store’s
  age, and the open list follows that fetch to its end; a closed list is fetched for and
  reads nothing until it opens.
- An origin branch is chosen by its ref and is named as the checkout names it.
- A row of the origin’s branches says where the reader’s own `origin/<branch>` is not
  where the origin’s is: “yours differs”, with the checkout’s commit in the row’s
  tooltip (`own`), and “not in checkout” for a branch the reader never fetched.
  The server says only that the two differ.
  `ownDifference` is what the tooltip says when the checkout’s commit is dated earlier
  or later than the origin’s, which the recording’s commits, all of one pinned date, are
  not.
- With no store, while it is first fetched, or when the origin needs credentials
  Metabrowser lacks, the list is the checkout’s own and says why.
- A mirror’s list, and a checkout that keeps no store, ask nothing and say nothing.

```console
$ node tests/dom/source-ref-selector-origin-session.js
{
  "steps": [
    {
      "step": "the working tree's tab reads no store, so it asks nothing",
      "requests": [
        "GET /api/source/refs?kind=working_tree"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
      "step": "the checkout's own branches read no store, so their list asks nothing",
      "requests": [
        "GET /api/source/refs?kind=branch"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "trunk 0b51e01 2020-01-01T00:00:00Z [checked out] (local chip)"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "the origin's branches are the store's, and the list says when it was fetched",
      "requests": [
        "GET /api/source/refs?kind=remote",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 38a3045 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T12:00:00Z) [quiet]",
        "error": null
      }
    },
    {
      "step": "the store was just fetched, so nothing is due and nothing is asked",
      "requests": [],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 38a3045 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T12:00:00Z) [quiet]",
        "error": null
      }
    },
    {
      "step": "the origin's tags are the store's, beside the tag only the checkout has",
      "requests": [
        "GET /api/source/refs?kind=tag"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "local-only 0b51e01 2020-01-01T00:00:00Z (tag chip)",
          "v2 fbc8399 2020-01-01T00:00:00Z (tag chip)"
        ],
        "note": "",
        "origin": "The origin's tags are as Metabrowser last fetched them (fetched 2026-09-17T12:00:00Z) [quiet]",
        "error": null
      }
    },
    {
      "step": "a fetch the ask started is followed: the list is asked for again",
      "requests": [
        "GET /api/source/refs?kind=remote"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 38a3045 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T12:00:00Z) [quiet]",
        "error": null
      }
    },
    {
      "step": "while the store is fetched, the open list asks again after a wait",
      "requests": [],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 38a3045 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T12:00:00Z) [quiet]",
        "error": null
      },
      "pullsPending": true
    },
    {
      "step": "the fetch ended: the origin's branch moved, and nothing more is asked",
      "requests": [
        "GET /api/source/refs?kind=remote"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 9ba2923 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T13:00:00Z) [quiet]",
        "error": null
      }
    },
    {
      "step": "Refresh reads the open list again, and one that says the same is not drawn",
      "requests": [
        "GET /api/source/refs?kind=remote"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 9ba2923 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T13:00:00Z) [quiet]",
        "error": null
      },
      "drawnAgain": 0
    },
    {
      "step": "Refresh asks for the origin's fetch, as the reader's own",
      "requests": [
        "POST /api/source/refresh {}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 9ba2923 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T13:00:00Z) [quiet]",
        "error": null
      }
    },
    {
      "step": "the fetch started, so the open list is asked for again",
      "requests": [
        "GET /api/source/refs?kind=remote"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 9ba2923 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T13:00:00Z) [quiet]",
        "error": null
      }
    },
    {
      "step": "the list says the fetch runs, and waits to ask again",
      "requests": [],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 38a3045 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T12:00:00Z) [quiet]",
        "error": null
      },
      "pullsPending": true
    },
    {
      "step": "the fetch ended, and the list is the origin's as just fetched",
      "requests": [
        "GET /api/source/refs?kind=remote"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 9ba2923 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T13:00:00Z) [quiet]",
        "error": null
      }
    },
    {
      "step": "with the list closed, Refresh fetches and lists nothing",
      "requests": [
        "POST /api/source/refresh {}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": false
      }
    },
    {
      "step": "an origin branch is asked for by its ref",
      "requests": [
        "POST /api/source/pin {\"ref\":\"refs/remotes/origin/trunk\",\"view\":\"/view/m\"}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
        "lists": [
          "working_tree",
          "branch",
          "remote",
          "tag"
        ],
        "kind": "remote",
        "query": "",
        "loading": false,
        "switching": true,
        "rows": [
          "origin/trunk 9ba2923 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T13:00:00Z) [quiet]",
        "error": null
      }
    },
    {
      "step": "the page goes to the same file in the origin's revision",
      "requests": [],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
        "lists": [
          "working_tree",
          "branch",
          "remote",
          "tag"
        ],
        "kind": "remote",
        "query": "",
        "loading": false,
        "switching": true,
        "rows": [
          "origin/trunk 9ba2923 2020-01-01T00:00:00Z [default] [yours differs] (remote chip)",
          "origin/feature f747860 2020-01-01T00:00:00Z [not in checkout] (remote chip)"
        ],
        "own": [
          "origin/trunk: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
          "origin/feature: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
        ],
        "note": "",
        "origin": "The origin's branches are as Metabrowser last fetched them (fetched 2026-09-17T13:00:00Z) [quiet]",
        "error": null
      },
      "navigated": [
        "/view/g1-bQ"
      ]
    },
    {
      "step": "the button names the origin's branch as the checkout names it",
      "requests": [],
      "filterPending": false,
      "paint": {
        "button": "Remote branch: origin/trunk",
        "open": false
      }
    },
    {
      "step": "while the store is first fetched, the list is the checkout's own",
      "requests": [
        "GET /api/source/refs?kind=remote",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 0b51e01 2020-01-01T00:00:00Z (remote chip)"
        ],
        "note": "",
        "origin": "Fetching the origin's branches. Until then these are the checkout's own. [quiet]",
        "error": null
      },
      "pullsPending": true
    },
    {
      "step": "with no store, the list is the checkout's own, and says so",
      "requests": [
        "GET /api/source/refs?kind=remote",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 0b51e01 2020-01-01T00:00:00Z (remote chip)"
        ],
        "note": "",
        "origin": "Origin not fetched. These are the checkout's own. [warning]",
        "error": null
      }
    },
    {
      "step": "an origin that needs credentials is not fetched, and the list says so",
      "requests": [
        "GET /api/source/refs?kind=remote",
        "POST /api/source/refresh {\"for\":\"page\"}"
      ],
      "filterPending": false,
      "paint": {
        "button": "Working tree · Branch: trunk",
        "open": true,
        "pullRequests": "none cached",
        "workingTree": "Working tree on trunk: /sandbox/checkout (kept whole: checkout) [current]",
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
          "origin/trunk 0b51e01 2020-01-01T00:00:00Z (remote chip)"
        ],
        "note": "",
        "origin": "Origin not fetched. These are the checkout's own. [warning]",
        "error": null
      }
    }
  ],
  "quietWithoutAStore": {
    "asked": [],
    "origin": null
  },
  "ownDifference": {
    "asRecorded": [
      "yours differs: Your checkout's origin/trunk is at another commit. This row is the origin's, as last fetched.",
      "not in checkout: Your checkout has no origin/feature of its own. This row is the origin's, as last fetched."
    ],
    "yoursEarlier": "yours differs: Your checkout's origin/trunk is at an earlier commit by date. This row is the origin's, as last fetched.",
    "yoursLater": "yours differs: Your checkout's origin/trunk is at a later commit by date. This row is the origin's, as last fetched.",
    "ownBranches": [
      null
    ]
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
