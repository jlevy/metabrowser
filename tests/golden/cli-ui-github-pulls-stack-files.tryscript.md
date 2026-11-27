---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Stack’s Combined Changed Files in the Pulls Tab

A stack’s Stack Overview row in the Pulls tab ends with the stack’s change line and a
chevron, and a press on them, or Space or Right on the row, lists the whole stack’s
changed files under it, in the tree a pull request’s row lists its own with (mb-odt4).
They are the files the stack’s own page lists in its Diff summary, from the same two
reads, which `builtin_plugins/github/stack-files.js` makes: the stack (`GET stack`),
then the stack’s comparison, once for each comparison.
This browserless session mounts the production tree controller
(`builtin_plugins/github/pull-files-tree.js`) on that list.
The stack’s answers are the route’s own, recorded in
`tests/fixtures/github-stack-responses.json`, and so is the comparison its `current`
answer names (`tests/fixtures/github-stack-comparison-responses.json`), whose rows the
diff view’s own `summaryRows` makes here, as it makes them for the panel: the Diff
summary’s rows of it, with their statuses and counts.
No comparison is recorded for the answer the stack moves to, so there each file the
answer names stands in for its row, with no counts.
The panel’s own step from the diff view to the tree runs only in a browser, where
`tests/test_github_stack_page_chrome.py` holds that the rows listed are the stack page’s
Diff summary’s.

`a stack's files` opens the tree on a stack whose members are not fetched yet: it asks
for each member and waits on its loading line; draws the stack’s files once the
comparison is there; reads the stack alone a freshness window on, and no comparison it
already read; reads the next comparison once when the stack moves; and says so, with
Retry, when the stack can no longer be shown as one comparison.
`a member that cannot be fetched` is a member still pending two reads after its fetch
ended: the tree says the list could not be had, and Retry asks for each member again.

```console
$ node tests/dom/github-pulls-stack-files-session.js
{
  "a stack's files": [
    {
      "step": "opened on a stack whose members are not fetched: it asks for each, and waits",
      "requests": [
        "GET /api/plugin/github/stack?number=70",
        "POST /api/plugin/github/pull-refresh {\"number\":8}",
        "POST /api/plugin/github/pull-refresh {\"number\":10}"
      ],
      "comparisons read": [],
      "label": "Changed files of Stack #70",
      "loading": true,
      "notice": null,
      "line": null,
      "rows": [],
      "next poll in": [
        1000
      ]
    },
    {
      "step": "the members arrive: the stack's comparison is read once, and its files are drawn",
      "requests": [
        "GET /api/plugin/github/stack?number=70"
      ],
      "comparisons read": [
        "<base>..<draft_"
      ],
      "label": "Changed files of Stack #70: 1 file",
      "loading": false,
      "notice": null,
      "line": null,
      "rows": [
        "v docs/ (1) +1",
        "  A draft.md +1"
      ],
      "next poll in": [
        60000
      ]
    },
    {
      "step": "a freshness window on, the same comparison: the stack is read, and nothing else",
      "requests": [
        "GET /api/plugin/github/stack?number=70"
      ],
      "comparisons read": [],
      "label": "Changed files of Stack #70: 1 file",
      "loading": false,
      "notice": null,
      "line": null,
      "rows": [
        "v docs/ (1) +1",
        "  A draft.md +1"
      ],
      "next poll in": [
        60000
      ]
    },
    {
      "step": "the stack moves: another comparison, read once, replaces the files",
      "requests": [
        "GET /api/plugin/github/stack?number=70",
        "GET /api/plugin/github/stack?number=70"
      ],
      "comparisons read": [
        "<base>..<fork_h"
      ],
      "label": "Changed files of Stack #70: 2 files",
      "loading": false,
      "notice": null,
      "line": null,
      "rows": [
        "v docs/ (1)",
        "  M new.md",
        "v src/ (1)",
        "  M app.txt"
      ],
      "next poll in": [
        60000
      ]
    },
    {
      "step": "the stack can no longer be shown as one comparison: no list, and Retry",
      "requests": [
        "GET /api/plugin/github/stack?number=70"
      ],
      "comparisons read": [],
      "label": "Changed files of Stack #70",
      "loading": false,
      "notice": "This stack cannot be shown as one comparison. [retry]",
      "line": null,
      "rows": [],
      "next poll in": [
        60000
      ]
    }
  ],
  "a member that cannot be fetched": [
    {
      "step": "opened on a pending stack: each member is asked for",
      "requests": [
        "GET /api/plugin/github/stack?number=70",
        "POST /api/plugin/github/pull-refresh {\"number\":8}",
        "POST /api/plugin/github/pull-refresh {\"number\":10}"
      ],
      "comparisons read": [],
      "label": "Changed files of Stack #70",
      "loading": true,
      "notice": null,
      "line": null,
      "rows": [],
      "next poll in": [
        1000
      ]
    },
    {
      "step": "one read on, still pending with no fetch running: it waits once more",
      "requests": [
        "GET /api/plugin/github/stack?number=70"
      ],
      "comparisons read": [],
      "label": "Changed files of Stack #70",
      "loading": true,
      "notice": null,
      "line": null,
      "rows": [],
      "next poll in": [
        1000
      ]
    },
    {
      "step": "two reads on: the fetch is taken as failed, and the tree offers Retry",
      "requests": [
        "GET /api/plugin/github/stack?number=70"
      ],
      "comparisons read": [],
      "label": "Changed files of Stack #70",
      "loading": false,
      "notice": "Could not list the changed files. [retry]",
      "line": null,
      "rows": [],
      "next poll in": [
        60000
      ]
    },
    {
      "step": "Retry asks for each member again, as a reader's retry",
      "requests": [
        "POST /api/plugin/github/pull-refresh {\"number\":8,\"retry\":true}",
        "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true}"
      ],
      "comparisons read": [],
      "label": "Changed files of Stack #70",
      "loading": true,
      "notice": null,
      "line": null,
      "rows": [],
      "next poll in": [
        1000
      ]
    }
  ]
}
? 0
```
