---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Source Ref Selector

A page on a served mirror’s pin shows a compact button naming the ref it was rendered
for. Opening it lists the mirror’s branches or tags from `/api/source/refs`, the default
branch first and the served ref marked; the filter box asks again after a pause in
typing, and an answer to an older filter never replaces a newer one.
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
`labels` is what the button says for a page on a tag, a pull request’s head, and a
commit with no ref.

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
          "topic 42382ea2303b [default] [current]",
          "feature c7ae2a331f54"
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
          "topic 42382ea2303b [default] [current]",
          "feature c7ae2a331f54"
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
          "feature c7ae2a331f54"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "an older answer does not replace a newer one",
      "requests": [
        "GET /api/source/refs?kind=branch&q=zzz",
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
          "feature c7ae2a331f54"
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
          "v1 fcb9d63c3c85"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "a list longer than a page says it stops short",
      "requests": [
        "GET /api/source/refs?kind=branch"
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
          "topic 42382ea2303b [default] [current]"
        ],
        "note": "Showing 1 of 2 branches; filter to narrow.",
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
      "step": "an answer after closing is dropped",
      "requests": [
        "GET /api/source/refs?kind=branch"
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
          "topic 42382ea2303b [default] [current]",
          "feature c7ae2a331f54"
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
          "topic 42382ea2303b [default] [current]",
          "feature c7ae2a331f54"
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
          "topic 42382ea2303b [default] [current]",
          "feature c7ae2a331f54"
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
    "Pull request: #7",
    "Commit: 42382ea2303b"
  ]
}
? 0
```
