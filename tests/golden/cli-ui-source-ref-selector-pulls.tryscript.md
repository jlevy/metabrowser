---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Source Ref Selector, Pull Requests

A branch that is the head of a pull request lists it on its row, and the filter box
finds a branch by its pull request’s number or title (`/api/source/refs`). The server
reads the pull requests from what its provider has cached and never fetches, so a list
opened before they are cached shows none, and asks again, quietly, every `PULLS_POLL_MS`
while the server says it is filling them: nothing is shown while it waits, a refused ask
leaves the rows, and closing the list cancels the wait.
An ask that finds the same listing draws nothing, so the rows keep their focus, their
tooltips, and a press in progress; one that finds pull requests for rows the list
already has patches them in.
An ask that comes due while a filter is typed waits for it.
While the server has only some of the pull requests, a filter says it may find more.

This browserless session loads the production `static/source-ref-selector.js` and plays
the server’s side from `tests/fixtures/source-ref-selector-responses.json`: what the
in-process application answered for a mirror whose repository’s catalog was empty, then
half full and still being filled, then whole.
`tests/test_source_ref_selector_session.py` replays them and fails when the recording
drifts. Each step records the requests the selector made, whether a filter pause or an
ask for pull requests is pending, and what it would paint: a row’s pull request is `|`,
its number, its state, and its title, with `+N` for the branch’s others.
`anchors` is where a list scrolls to when its rows are laid out again, as they are when
pull requests arrive for rows above the view and make those rows taller
(`anchoredScroll`): the row at the top of the view stays where it was, the foot stays
the foot, and a focused row stays in view.
`same` is which answers of the route say the same, so that one asked for again draws
nothing (`sameListing`).

```console
$ node tests/dom/source-ref-selector-pulls-session.js
{
  "steps": [
    {
      "step": "pull requests not cached yet: the rows show none, and the list will ask again",
      "requests": [
        "GET /api/source/refs?kind=branch"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "pullRequests": "none cached, filling",
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
      },
      "pullsPending": true
    },
    {
      "step": "asking again shows nothing while it waits",
      "requests": [
        "GET /api/source/refs?kind=branch"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "pullRequests": "none cached, filling",
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
      "step": "a branch shows the pull requests the server has, and it asks again until it has all",
      "requests": [],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "filter": "Filter branches or pull requests",
        "pullRequests": "partly cached, filling",
        "kind": "branch",
        "query": "",
        "loading": false,
        "switching": false,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current] | #12 merged Start the topic",
          "feature c7ae2a3 2026-01-01T02:00:00Z | #18 closed Try the first design"
        ],
        "note": "",
        "error": null
      },
      "pullsPending": true
    },
    {
      "step": "an ask that is refused leaves the rows as they are and asks no more",
      "requests": [
        "GET /api/source/refs?kind=branch"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "filter": "Filter branches or pull requests",
        "pullRequests": "partly cached, filling",
        "kind": "branch",
        "query": "",
        "loading": false,
        "switching": false,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current] | #12 merged Start the topic",
          "feature c7ae2a3 2026-01-01T02:00:00Z | #18 closed Try the first design"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "a full cache lists each branch's pull requests, open first, and asks no more",
      "requests": [
        "GET /api/source/refs?kind=branch"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "filter": "Filter branches or pull requests",
        "pullRequests": "cached",
        "kind": "branch",
        "query": "",
        "loading": false,
        "switching": false,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current] | #12 merged Start the topic",
          "feature c7ae2a3 2026-01-01T02:00:00Z | #21 open feat(ref): choose among branches +1"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "the filter finds a branch by its pull request's number",
      "requests": [
        "GET /api/source/refs?kind=branch&q=%231"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "filter": "Filter branches or pull requests",
        "pullRequests": "cached",
        "kind": "branch",
        "query": "#1",
        "loading": false,
        "switching": false,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current] | #12 merged Start the topic",
          "feature c7ae2a3 2026-01-01T02:00:00Z | #18 closed Try the first design +1"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "and by the words of its title, whatever its name says",
      "requests": [
        "GET /api/source/refs?kind=branch&q=start+the"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "filter": "Filter branches or pull requests",
        "pullRequests": "cached",
        "kind": "branch",
        "query": "start the",
        "loading": false,
        "switching": false,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current] | #12 merged Start the topic"
        ],
        "note": "",
        "error": null
      }
    },
    {
      "step": "a list of tags has no pull requests, and the filter finds tags",
      "requests": [
        "GET /api/source/refs?kind=tag&q=start+the"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "kind": "tag",
        "query": "start the",
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
      "step": "the server has half its pull requests, and is filling the rest",
      "requests": [
        "GET /api/source/refs?kind=branch"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "filter": "Filter branches or pull requests",
        "pullRequests": "partly cached, filling",
        "kind": "branch",
        "query": "",
        "loading": false,
        "switching": false,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current] | #12 merged Start the topic",
          "feature c7ae2a3 2026-01-01T02:00:00Z | #18 closed Try the first design"
        ],
        "note": "",
        "error": null
      },
      "pullsPending": true
    },
    {
      "step": "an ask that finds the listing unchanged draws nothing",
      "requests": [
        "GET /api/source/refs?kind=branch"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "filter": "Filter branches or pull requests",
        "pullRequests": "partly cached, filling",
        "kind": "branch",
        "query": "",
        "loading": false,
        "switching": false,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current] | #12 merged Start the topic",
          "feature c7ae2a3 2026-01-01T02:00:00Z | #18 closed Try the first design"
        ],
        "note": "",
        "error": null
      },
      "pullsPending": true,
      "rendered": 0
    },
    {
      "step": "an ask that comes due while a filter is typed waits for it",
      "requests": [],
      "filterPending": true,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "filter": "Filter branches or pull requests",
        "pullRequests": "partly cached, filling",
        "kind": "branch",
        "query": "",
        "loading": false,
        "switching": false,
        "rows": [
          "topic 42382ea 2026-01-01T01:00:00Z [default] [current] | #12 merged Start the topic",
          "feature c7ae2a3 2026-01-01T02:00:00Z | #18 closed Try the first design"
        ],
        "note": "",
        "error": null
      },
      "pullsPending": true
    },
    {
      "step": "the filter finds what is cached, and the list says it may find more",
      "requests": [
        "GET /api/source/refs?kind=branch&q=try"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "filter": "Filter branches or pull requests",
        "pullRequests": "partly cached, filling",
        "kind": "branch",
        "query": "try",
        "loading": false,
        "switching": false,
        "rows": [
          "feature c7ae2a3 2026-01-01T02:00:00Z | #18 closed Try the first design"
        ],
        "note": "Some pull requests are still loading, so more branches may match.",
        "error": null
      },
      "pullsPending": true
    },
    {
      "step": "a filter that finds nothing says so, and that it may find more later",
      "requests": [
        "GET /api/source/refs?kind=branch&q=zzz"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": true,
        "filter": "Filter branches or pull requests",
        "pullRequests": "partly cached, filling",
        "kind": "branch",
        "query": "zzz",
        "loading": false,
        "switching": false,
        "rows": [],
        "note": "No branches match. Some pull requests are still loading, so more branches may match.",
        "error": null
      },
      "pullsPending": true
    },
    {
      "step": "closing stops asking for pull requests",
      "requests": [
        "GET /api/source/refs?kind=branch"
      ],
      "filterPending": false,
      "paint": {
        "button": "Branch: topic",
        "open": false
      }
    }
  ],
  "anchors": [
    "at the top, nothing above to move: 0 -> 0 px, the row at the top 0 -> 0 (its top 0 -> 0)",
    "the top row stays where it was while rows above it grow: 570 -> 660 px, the row at the top 20 -> 20 (its top 560 -> 650)",
    "rows that are the same stay where they are: 560 -> 560 px, the row at the top 20 -> 20 (its top 560 -> 560)",
    "the foot stays the foot, as End left it: 2688 -> 2778 px, the row at the top 96 -> 96 (its top 2688 -> 2778)",
    "a focused row in view stays in view: 560 -> 946 px, the row at the top 20 -> 20 (its top 560 -> 920)",
    "a focused row out of view is left where it is: 1680 -> 2130 px, the row at the top 60 -> 60 (its top 1680 -> 2130)",
    "a list that shrinks to three rows: 1400 -> 0 px"
  ],
  "same": [
    "the same answer: same",
    "a pull request's title changed: different",
    "the server began filling its pull requests: different",
    "no answer and an answer: different",
    "a row fewer: different",
    "the same refs with other pull requests: same",
    "a ref's commit moved: different",
    "a row fewer: different"
  ]
}
? 0
```
