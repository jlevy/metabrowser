---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Pull Request’s Changed Files as a Tree

Expanding a row of the Pulls tab shows the pull request’s changed files as a tree, built
from the list `GET /api/plugin/github/pull-files` answers and never from hydrated diff
documents. This browserless session loads the production
`builtin_plugins/github/pull-files-tree.js`, with `pulls-panel.js` for the words a
failed refresh is given, and plays answers the route gave while a fake `gh` replayed
full-size pages, recorded in `tests/fixtures/github-pull-files-responses.json`.

`a list fills page by page` is pull request 106’s first list, read between its pages:
each step says the window the tree asked for, which is past the rows it holds while the
same list fills, the honest count, with the pages GitHub’s `Link` header counted, and
the rows. A folder whose only child is a folder is one row, `src/app/plugins/github`,
until the third page brings `src/app/views` and the chain splits.
How folders start is decided by the list’s size, the pages GitHub counted included: open
under the threshold, and only the top level over it.
A reader’s toggle of a chain row opens or closes every folder in it, and the file a page
shows is revealed and marked current.
A path is the identity, with its characters intact, and the name is the server’s
display, with control and invisible characters shown as U+FFFD. The other stories are
each kind of list and each way a refresh can end, and `invariants` are the relations
`tests/test_github_pull_files_tree_session.py` holds.

```console
$ node tests/dom/github-pull-files-tree-session.js
{
  "stories": {
    "a list fills page by page": [
      {
        "answer": "absent",
        "asked": "number=106&offset=0",
        "window": "offset 0, 0 rows",
        "changed": false,
        "status": "absent",
        "reason": "not_cached",
        "count": null,
        "capped": false,
        "truncated": false,
        "failure": null,
        "says": null,
        "rows": []
      },
      {
        "answer": "filling 0",
        "asked": "number=106&offset=0",
        "window": "offset 0, 0 rows",
        "changed": false,
        "status": "pending",
        "reason": null,
        "count": null,
        "capped": false,
        "truncated": false,
        "failure": null,
        "says": null,
        "rows": []
      },
      {
        "answer": "filling 1",
        "asked": "number=106&offset=0",
        "window": "offset 0, 100 rows",
        "changed": true,
        "status": "filling",
        "reason": null,
        "count": "100 files so far, 1 of 3 pages",
        "capped": false,
        "truncated": false,
        "failure": null,
        "says": null,
        "rows": [
          "v assets/ (1)",
          "  M logo.png +0 -0",
          "v docs/ (2)",
          "  R guide.md (from docs/old-guide.md) +3 -0",
          "  D removed.md +0 -12",
          "v src/app/plugins/github/ (96)",
          "  M mod_000.py +4 -2",
          "  M mod_001.py +4 -2",
          "  M mod_002.py +4 -2",
          "  … 91 more",
          "  M mod_094.py +4 -2",
          "  M mod_095.py +4 -2",
          "M README.md +2 -1"
        ]
      },
      {
        "answer": "filling 2",
        "asked": "number=106&offset=100",
        "window": "offset 100, 100 rows",
        "changed": true,
        "status": "filling",
        "reason": null,
        "count": "200 files so far, 2 of 3 pages",
        "capped": false,
        "truncated": false,
        "failure": null,
        "says": null,
        "rows": [
          "v assets/ (1)",
          "  M logo.png +0 -0",
          "v docs/ (2)",
          "  R guide.md (from docs/old-guide.md) +3 -0",
          "  D removed.md +0 -12",
          "v src/app/plugins/github/ (196)",
          "  M mod_000.py +4 -2",
          "  M mod_001.py +4 -2",
          "  M mod_002.py +4 -2",
          "  … 191 more",
          "  M mod_194.py +4 -2",
          "  M mod_195.py +4 -2",
          "M README.md +2 -1"
        ]
      },
      {
        "answer": "filled",
        "asked": "number=106&offset=200",
        "window": "offset 200, 49 rows",
        "changed": true,
        "status": "current",
        "reason": null,
        "count": "249 files",
        "capped": false,
        "truncated": false,
        "failure": null,
        "says": null,
        "rows": [
          "v assets/ (1)",
          "  M logo.png +0 -0",
          "v docs/ (2)",
          "  R guide.md (from docs/old-guide.md) +3 -0",
          "  D removed.md +0 -12",
          "v src/app/ (242)",
          "  v plugins/github/ (240)",
          "    M mod_000.py +4 -2",
          "    M mod_001.py +4 -2",
          "    M mod_002.py +4 -2",
          "    … 235 more",
          "    M mod_238.py +4 -2",
          "    A pull_files.py +120 -0",
          "  v views/ (2)",
          "    M one.py +1 -1",
          "    A two.py +9 -0",
          "v tools/new/ (1)",
          "  R script.sh (from scripts/script.sh) +0 -0",
          "v weird/ (2)",
          "  A bell�name.txt +1 -0",
          "  M zero�width.md +1 -1",
          "M README.md +2 -1"
        ]
      }
    ],
    "same-second equally sized refreshes replace the held list": {
      "atOldEnd": "number=106&offset=1",
      "restart": "number=106&offset=0",
      "rows": [
        "after.js"
      ]
    },
    "only file-address expansions close when the page moves": [
      {
        "expand": [
          7
        ],
        "collapse": []
      },
      {
        "expand": [
          8
        ],
        "collapse": [
          7
        ]
      },
      {
        "expand": [
          9
        ],
        "collapse": []
      }
    ],
    "a long tree draws only its viewport and overscan": [
      {
        "start": 0,
        "end": 70
      },
      {
        "start": 460,
        "end": 570
      },
      {
        "start": 4539,
        "end": 4539
      }
    ],
    "a chain row toggles as one": {
      "closed": [
        "v assets/ (1)",
        "  M logo.png +0 -0",
        "v docs/ (2)",
        "  R guide.md (from docs/old-guide.md) +3 -0",
        "  D removed.md +0 -12",
        "> src/app/ (242)",
        "v tools/new/ (1)",
        "  R script.sh (from scripts/script.sh) +0 -0",
        "v weird/ (2)",
        "  A bell�name.txt +1 -0",
        "  M zero�width.md +1 -1",
        "M README.md +2 -1"
      ],
      "reopened": [
        "v assets/ (1)",
        "  M logo.png +0 -0",
        "v docs/ (2)",
        "  R guide.md (from docs/old-guide.md) +3 -0",
        "  D removed.md +0 -12",
        "v src/app/ (242)",
        "  v plugins/github/ (240)",
        "    M mod_000.py +4 -2"
      ]
    },
    "past the threshold only the top level shows": [
      "> assets/ (1)",
      "> docs/ (2)",
      "> src/app/ (242)",
      "> tools/new/ (1)",
      "> weird/ (2)",
      "M README.md +2 -1"
    ],
    "the file a page shows is revealed and current": [
      "> assets/ (1)",
      "> docs/ (2)",
      "> src/app/ (242)",
      "> tools/new/ (1)",
      "v weird/ (2)",
      "  A bell�name.txt +1 -0  <- current",
      "  M zero�width.md +1 -1",
      "M README.md +2 -1"
    ],
    "a name is the server's display, and its path the identity": [
      {
        "path": "weird/bell<U+0007>name.txt",
        "name": "bell�name.txt",
        "badge": "A",
        "label": "Added"
      },
      {
        "path": "weird/zero<U+200B>width.md",
        "name": "zero�width.md",
        "badge": "M",
        "label": "Modified"
      }
    ],
    "an unchanged head with a different local base starts again at zero": "number=7&offset=0",
    "a list from the local comparison": {
      "status": "current",
      "reason": null,
      "count": "2 files",
      "capped": false,
      "truncated": false,
      "failure": null,
      "says": null,
      "rows": [
        "v docs/ (1)",
        "  A new.md +1 -0",
        "v src/ (1)",
        "  M app.txt +1 -0"
      ]
    },
    "GitHub stops at 3,000 files": {
      "status": "current",
      "reason": null,
      "count": "3,000 files, the most GitHub lists",
      "capped": true,
      "truncated": false,
      "failure": null,
      "says": null
    },
    "a list asked for and not yet arrived": {
      "status": "pending",
      "reason": null,
      "count": null,
      "capped": false,
      "truncated": false,
      "failure": null,
      "says": null
    },
    "a list that stopped part-way": {
      "status": "stopped",
      "reason": null,
      "count": "200 files so far, 2 of 3 pages",
      "capped": false,
      "truncated": false,
      "failure": "rate_limited",
      "says": "GitHub's rate limit lifts at 2026-09-23T16:46:00Z. No automatic attempt runs before then."
    },
    "a list the pull request has changed since": {
      "status": "stale",
      "reason": null,
      "count": "249 files",
      "capped": false,
      "truncated": false,
      "failure": "cache_unwritable",
      "says": "The list of changed files could not be written to the cache."
    },
    "a server with no GitHub repository": {
      "status": "absent",
      "reason": "not_github",
      "count": null,
      "capped": false,
      "truncated": false,
      "failure": null,
      "says": null
    },
    "each way a refresh can fail": {
      "not_logged_in": {
        "status": "current",
        "reason": null,
        "count": "249 files",
        "capped": false,
        "truncated": false,
        "failure": "not_logged_in",
        "says": "GitHub CLI is not signed in to github.com. Run gh auth login --hostname github.com, then retry. You can still browse local files and any cached pull requests."
      },
      "gh_too_old": {
        "status": "stale",
        "reason": null,
        "count": "249 files",
        "capped": false,
        "truncated": false,
        "failure": "gh_too_old",
        "says": "This GitHub CLI cannot report the active account. Update gh from https://cli.github.com/, then run gh auth status --hostname github.com. You can still browse local files and any cached pull requests."
      },
      "not_found_or_private": {
        "status": "stale",
        "reason": null,
        "count": "249 files",
        "capped": false,
        "truncated": false,
        "failure": "not_found_or_private",
        "says": "The pull request was not found, or the signed-in account cannot read its files."
      },
      "network_error": {
        "status": "stale",
        "reason": null,
        "count": "249 files",
        "capped": false,
        "truncated": false,
        "failure": "network_error",
        "says": "Offline, or GitHub could not be reached. The files are as they were last listed."
      },
      "gh_failed": {
        "status": "stale",
        "reason": null,
        "count": "249 files",
        "capped": false,
        "truncated": false,
        "failure": "gh_failed",
        "says": "GitHub answered with something other than JSON."
      },
      "account_changed": {
        "status": "stale",
        "reason": null,
        "count": "249 files",
        "capped": false,
        "truncated": false,
        "failure": "account_changed",
        "says": "The active gh account changed during the read, so it is not taken as complete; open the files again."
      },
      "rate_limited": {
        "status": "stale",
        "reason": null,
        "count": "249 files",
        "capped": false,
        "truncated": false,
        "failure": "rate_limited",
        "says": "GitHub's rate limit lifts at 2026-09-17T12:14:06Z. No automatic attempt runs before then."
      },
      "gh_missing": {
        "status": "stale",
        "reason": null,
        "count": "249 files",
        "capped": false,
        "truncated": false,
        "failure": "gh_missing",
        "says": "Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com. You can still browse local files and any cached pull requests."
      },
      "cache_unwritable": {
        "status": "stale",
        "reason": null,
        "count": "249 files",
        "capped": false,
        "truncated": false,
        "failure": "cache_unwritable",
        "says": "The list of changed files could not be written to the cache."
      }
    },
    "an answer for another read starts again at 0": {
      "joined": false,
      "asked": "number=106&offset=0",
      "held": 100
    }
  },
  "controller": [
    {
      "step": "a failed first read offers Retry and keeps reading",
      "requests": [
        "GET /api/plugin/github/pull-files?number=106&offset=0"
      ],
      "held": 0,
      "current": null,
      "notice": "The server did not answer.",
      "timers": [
        1000
      ]
    },
    {
      "step": "Retry reads the cache and automatically lists missing files",
      "requests": [
        "GET /api/plugin/github/pull-files?number=106&offset=0",
        "POST /api/plugin/github/pull-files-refresh {\"number\":106,\"retry\":false}"
      ],
      "held": 0,
      "current": null,
      "notice": null,
      "timers": [
        1000
      ]
    },
    {
      "step": "filling 1",
      "requests": [
        "GET /api/plugin/github/pull-files?number=106&offset=0"
      ],
      "held": 100,
      "current": null,
      "notice": null,
      "timers": [
        1000
      ]
    },
    {
      "step": "filling 2",
      "requests": [
        "GET /api/plugin/github/pull-files?number=106&offset=100"
      ],
      "held": 200,
      "current": null,
      "notice": null,
      "timers": [
        1000
      ]
    },
    {
      "step": "filled",
      "requests": [
        "GET /api/plugin/github/pull-files?number=106&offset=200"
      ],
      "held": 249,
      "current": null,
      "notice": null,
      "timers": [
        60000
      ]
    },
    {
      "step": "held keys jump every file but replace history once on release",
      "jumps": 5,
      "opens": [
        {
          "file": "src/app/plugins/github/mod_002.py",
          "replace": true,
          "jumped": true
        }
      ]
    },
    {
      "step": "Enter pushes the focused file",
      "opens": [
        {
          "file": "src/app/plugins/github/mod_002.py",
          "replace": false,
          "jumped": false
        }
      ]
    },
    {
      "step": "a file reported by the page is revealed without moving its address",
      "requests": [],
      "held": 249,
      "current": "weird/bell\u0007name.txt",
      "notice": null,
      "timers": [
        60000
      ]
    },
    {
      "step": "the walk's own scroll report does not cancel its final address",
      "opens": [
        {
          "file": "docs/removed.md",
          "replace": true,
          "jumped": true
        }
      ]
    },
    {
      "step": "a later route cancels a pending file walk",
      "requests": [],
      "held": 249,
      "current": "weird/bell\u0007name.txt",
      "notice": null,
      "timers": [
        60000
      ]
    },
    {
      "step": "hiding the panel cancels a pending file walk",
      "requests": [],
      "held": 249,
      "current": "docs/removed.md",
      "notice": null,
      "timers": []
    },
    {
      "step": "a closed or hidden tree has no timer",
      "requests": [],
      "held": 249,
      "current": "docs/removed.md",
      "notice": null,
      "timers": []
    }
  ],
  "invariants": {
    "filled rows are the list's rows": true,
    "no single-child folder is its own row": true,
    "each folder counts the files under it": true,
    "every name is the server's display": true,
    "a list for another read starts again at 0": true
  }
}
? 0
```
