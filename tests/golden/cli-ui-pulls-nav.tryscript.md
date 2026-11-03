---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Pulls Tab’s Host

The server writes the Pulls tab into a shell whose served root is a GitHub repository,
and `static/pulls-nav.js` into that shell’s `shell-tools` bundle, so a folder fetches
none of it and the decision costs no request.
What is left is the host’s: which tab an address shows, mounting on demand the view a
plugin registers for the `pull-request-list` kind, telling it when it is shown and
hidden, and the keys of its rows, whose text the shortcut registry owns.

This browserless session loads the production `static/pulls-nav.js`, with the real
`static/pull-route.js` and `static/keyboard-shortcuts.js`, and plays the shell and the
view. `addresses` is what each address names and which tab it asks for from each tab in
front, `null` being none: a pull request’s address shows Pulls, a file’s address moves
Pulls off the front, and a commit’s is the Git panel’s. `stories` is what the host asked
of each, in order: a page elsewhere on a mirror, which reads the view ahead when the
shell is idle; the first page of a pull request’s address, which the server drew with
the tab in front; Back between the list’s filters, each a place of its own, which shows
the list though Files was chosen by hand; a load that fails, which says so only to a
reader looking and tries again on the next show; and a page that goes while the view
loads, whose late mount is disposed.
`keys` is each key through the real registry and what it told the view, and `help` is
what Help reads for the group.
`the page’s host` is the module’s own `init` and `dispose` on a page it is played: the
listeners it adds, that only a walking key’s release ends a walk, and that an `init`
after a `dispose` listens again.

```console
$ node tests/dom/pulls-nav-session.js
{
  "the page's host": {
    "init listens": [
      "the tab: focusin",
      "the tab: focusout",
      "the tab: keyup",
      "the window: popstate"
    ],
    "a modifier's release ends no walk": [],
    "J's release ends it": [
      "released"
    ],
    "dispose ends them all": {
      "listening": [],
      "told": [
        "view disposed",
        "tab removed"
      ]
    },
    "init again listens again": [
      "the tab: focusin",
      "the tab: focusout",
      "the tab: keyup",
      "the window: popstate"
    ],
    "and J's release ends a walk again": [
      "released"
    ]
  },
  "addresses": {
    "/pulls": {
      "names": {
        "page": null,
        "filter": "all"
      },
      "from Files": "pulls",
      "from Pulls": null,
      "from Git": "pulls"
    },
    "/pulls?state=closed": {
      "names": {
        "page": null,
        "filter": "closed"
      },
      "from Files": "pulls",
      "from Pulls": null,
      "from Git": "pulls"
    },
    "/pulls?state=merged": {
      "names": {
        "page": null,
        "filter": "all"
      },
      "from Files": "pulls",
      "from Pulls": null,
      "from Git": "pulls"
    },
    "/pull/7": {
      "names": {
        "page": 7,
        "filter": null
      },
      "from Files": "pulls",
      "from Pulls": null,
      "from Git": "pulls"
    },
    "/pull/7/files": {
      "names": {
        "page": 7,
        "filter": null
      },
      "from Files": "pulls",
      "from Pulls": null,
      "from Git": "pulls"
    },
    "/view/README.md": {
      "names": null,
      "from Files": null,
      "from Pulls": "files",
      "from Git": null
    },
    "/commit/abc": {
      "names": null,
      "from Files": null,
      "from Pulls": null,
      "from Git": null
    }
  },
  "stories": {
    "a mirror's page at a file": [
      {
        "the shell starts it": [
          "registered pulls \"Pulls\"",
          "prefetch scheduled"
        ],
        "snapshot": {
          "mounted": false,
          "mounting": false,
          "shown": false,
          "disposed": false
        }
      },
      {
        "the idle read mounts it, hidden": [
          "load view of pull-request-list",
          "view rendered: filter all, current null, shown false, kind pull-request-list",
          "view told: hidden",
          "view told: current null"
        ],
        "snapshot": {
          "mounted": true,
          "mounting": false,
          "shown": false,
          "disposed": false
        }
      },
      {
        "the tab opens: it is told, and loads nothing": [
          "activated pulls",
          "view told: shown"
        ]
      },
      {
        "another tab: it is told": [
          "activated files",
          "view told: hidden"
        ]
      },
      {
        "the page goes: it is disposed": [
          "view disposed"
        ],
        "snapshot": {
          "mounted": false,
          "mounting": false,
          "shown": false,
          "disposed": true
        }
      }
    ],
    "the first page of a pull request's address": [
      {
        "the tab shows, mounted at once": [
          "registered pulls \"Pulls\"",
          "activated pulls",
          "load view of pull-request-list",
          "view rendered: filter all, current 7, shown true, kind pull-request-list",
          "view told: shown",
          "view told: current 7"
        ],
        "snapshot": {
          "mounted": true,
          "mounting": false,
          "shown": true,
          "disposed": false
        }
      },
      {
        "another pull request: the row follows": [
          "view told: current 8"
        ]
      },
      {
        "the list's address: its filter": [
          "view told: current null",
          "view told: filter open"
        ]
      },
      {
        "a filter chosen at the list's address is an address": [
          "pushed /pulls?state=closed"
        ]
      },
      {
        "a filter chosen on a pull request's page is the panel's": []
      },
      {
        "a row's open is the shell's": [
          "opened pull request 9"
        ]
      },
      {
        "a file opens: Files is in front": [
          "activated files",
          "view told: hidden",
          "view told: current null"
        ]
      },
      {
        "chosen by hand at that file: a step on the same path keeps it": [
          "view told: current null"
        ]
      },
      {
        "a commit is the Git panel's": [
          "view told: current null"
        ]
      },
      {
        "history lands on a pull request from Files": [
          "activated pulls",
          "view told: shown",
          "view told: current 7"
        ]
      }
    ],
    "Back between the list's filters": [
      {
        "Files chosen by hand at Open: the same place keeps it": [
          "view told: current null",
          "view told: filter open"
        ]
      },
      {
        "Back to All: the list is in front": [
          "activated pulls",
          "view told: shown",
          "view told: current null",
          "view told: filter all"
        ]
      },
      {
        "Back from a filter the panel chose: the list again": [
          "activated pulls",
          "view told: shown",
          "view told: current null",
          "view told: filter all"
        ]
      }
    ],
    "a view that could not load": [
      {
        "the tab opens, and the load fails": [
          "activated pulls",
          "prefetch cancelled",
          "load view of pull-request-list",
          "failure shown"
        ],
        "snapshot": {
          "mounted": false,
          "mounting": false,
          "shown": true,
          "disposed": false
        }
      },
      {
        "the next show tries again": [
          "activated files",
          "activated pulls",
          "load view of pull-request-list",
          "view rendered: filter all, current null, shown true, kind pull-request-list",
          "view told: shown",
          "view told: current null"
        ],
        "snapshot": {
          "mounted": true,
          "mounting": false,
          "shown": true,
          "disposed": false
        }
      }
    ],
    "a read ahead that could not load": [
      {
        "nothing is shown of it": [
          "load view of pull-request-list"
        ],
        "snapshot": {
          "mounted": false,
          "mounting": false,
          "shown": false,
          "disposed": false
        }
      }
    ],
    "the page goes while the view loads": [
      {
        "the late mount is disposed": [
          "view rendered: filter all, current 7, shown false, kind pull-request-list",
          "view disposed"
        ],
        "snapshot": {
          "mounted": false,
          "mounting": false,
          "shown": false,
          "disposed": true
        }
      }
    ]
  },
  "keys": {
    "ArrowDown": {
      "handled": true,
      "did": [
        "view told: move 1"
      ]
    },
    "held J": {
      "handled": true,
      "did": [
        "view told: move 1 repeating"
      ]
    },
    "ArrowUp": {
      "handled": true,
      "did": [
        "view told: move -1"
      ]
    },
    "held K": {
      "handled": true,
      "did": [
        "view told: move -1 repeating"
      ]
    },
    "Enter": {
      "handled": true,
      "did": [
        "view told: open the row with focus"
      ]
    }
  },
  "help": {
    "label": "Pull requests",
    "context": "Available while a pull-request row has focus.",
    "commands": [
      {
        "keys": "Up arrow or K",
        "action": "Previous pull request",
        "description": "Open the previous pull request in the list."
      },
      {
        "keys": "Down arrow or J",
        "action": "Next pull request",
        "description": "Open the next pull request in the list."
      },
      {
        "keys": "Enter or Space",
        "action": "Open pull request",
        "description": "Open the focused pull request."
      }
    ]
  },
  "keys when no row has focus": false,
  "groups once unregistered": []
}
? 0
```
