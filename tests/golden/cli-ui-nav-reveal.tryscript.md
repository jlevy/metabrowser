---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Navigation Reveals the Item

Navigating to an item by any route shows it in the navigation pane: its tab comes to the
front, and the tab’s panel opens the folders or stack that hold it, selects it, and
scrolls it into view, without moving focus from where the reader is reading
([Navigation Reveals the Item](../../docs/design-system.md#navigation-reveals-the-item)).

This browserless session runs the production code that decides it.
`rule` is `static/main-tabs.js`’s one rule through its exports and the real address
parser: which tab holds what each address names, and for each route, from another tab,
whether the tab switches, whether its panel reveals, and whether the reveal scrolls.
Only a tab’s own button or letter keeps the panel’s place, and only a step within the
item shown, such as a fragment, reveals nothing.
`landing` is how the shell names a file landing’s route from the navigation controller’s
source. `tabs` loads `static/main-tabs.js` and `static/pulls-nav.js` whole over a
stand-in DOM, with `app.js`’s pull-request routes lifted verbatim, and plays each route
as `app.js` calls it, printing the tab in front, what each panel was asked, and when the
Pulls tab’s own controller reveals a row.
Another tab or a changed file of the pull request shown is a step within it and reveals
no row; Quick Search for it reveals it again, after the tab’s button too; no step moves
focus. `files tree` lifts `app.js`’s tree reveal verbatim over a stand-in tree: closed
folders open, the page of a long folder that holds the row is drawn, a reveal that
cannot show its row leaves no other row selected, and the tree says a file is outside
the filter only when the filter is what hides it.
`pulls list` runs the Pulls tab’s controller over the recorded lists and stack snapshot:
an address naming a pull request in a closed stack opens the stack, the same pull
request named again moves nothing unless it was opened again, which reveals it and ends
a tab landing’s kept place, one the list does not hold is named under the band, and
under All the list reads on for one past the rows it has read.

```console
$ node tests/dom/nav-reveal-session.js
{
  "rule": {
    "/view/docs/deep/leaf.md": {
      "tab": "files",
      "open, from pulls": "switch to files, reveal, scroll nearest",
      "address, from pulls": "switch to files, reveal, scroll nearest",
      "history, from pulls": "switch to files, reveal, scroll nearest",
      "nav, from pulls": "switch to files, reveal, scroll nearest",
      "tab, from pulls": "switch to files, reveal, scroll keep",
      "step, from pulls": "switch to files, no reveal",
      "open, from files": "stay on files, reveal, scroll nearest"
    },
    "/view/docs/": {
      "tab": "files",
      "open, from pulls": "switch to files, reveal, scroll nearest",
      "address, from pulls": "switch to files, reveal, scroll nearest",
      "history, from pulls": "switch to files, reveal, scroll nearest",
      "nav, from pulls": "switch to files, reveal, scroll nearest",
      "tab, from pulls": "switch to files, reveal, scroll keep",
      "step, from pulls": "switch to files, no reveal",
      "open, from files": "stay on files, reveal, scroll nearest"
    },
    "/view/": {
      "tab": "files",
      "open, from pulls": "switch to files, reveal, scroll nearest",
      "address, from pulls": "switch to files, reveal, scroll nearest",
      "history, from pulls": "switch to files, reveal, scroll nearest",
      "nav, from pulls": "switch to files, reveal, scroll nearest",
      "tab, from pulls": "switch to files, reveal, scroll keep",
      "step, from pulls": "switch to files, no reveal",
      "open, from files": "stay on files, reveal, scroll nearest"
    },
    "/pull/7": {
      "tab": "pulls",
      "open, from files": "switch to pulls, reveal, scroll nearest",
      "address, from files": "switch to pulls, reveal, scroll nearest",
      "history, from files": "switch to pulls, reveal, scroll nearest",
      "nav, from files": "switch to pulls, reveal, scroll nearest",
      "tab, from files": "switch to pulls, reveal, scroll keep",
      "step, from files": "switch to pulls, no reveal",
      "open, from pulls": "stay on pulls, reveal, scroll nearest"
    },
    "/pull/7/files/src/app.txt": {
      "tab": "pulls",
      "open, from files": "switch to pulls, reveal, scroll nearest",
      "address, from files": "switch to pulls, reveal, scroll nearest",
      "history, from files": "switch to pulls, reveal, scroll nearest",
      "nav, from files": "switch to pulls, reveal, scroll nearest",
      "tab, from files": "switch to pulls, reveal, scroll keep",
      "step, from files": "switch to pulls, no reveal",
      "open, from pulls": "stay on pulls, reveal, scroll nearest"
    },
    "/pulls?state=closed": {
      "tab": "pulls",
      "open, from files": "switch to pulls, reveal, scroll nearest",
      "address, from files": "switch to pulls, reveal, scroll nearest",
      "history, from files": "switch to pulls, reveal, scroll nearest",
      "nav, from files": "switch to pulls, reveal, scroll nearest",
      "tab, from files": "switch to pulls, reveal, scroll keep",
      "step, from files": "switch to pulls, no reveal",
      "open, from pulls": "stay on pulls, reveal, scroll nearest"
    },
    "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": {
      "tab": "git",
      "open, from pulls": "switch to git, reveal, scroll nearest",
      "address, from pulls": "switch to git, reveal, scroll nearest",
      "history, from pulls": "switch to git, reveal, scroll nearest",
      "nav, from pulls": "switch to git, reveal, scroll nearest",
      "tab, from pulls": "switch to git, reveal, scroll keep",
      "step, from pulls": "switch to git, no reveal",
      "open, from git": "stay on git, reveal, scroll nearest"
    },
    "/view/ (the neutral Commits entry)": {
      "tab": "git",
      "open, from pulls": "switch to git, reveal, scroll nearest",
      "address, from pulls": "switch to git, reveal, scroll nearest",
      "history, from pulls": "switch to git, reveal, scroll nearest",
      "nav, from pulls": "switch to git, reveal, scroll nearest",
      "tab, from pulls": "switch to git, reveal, scroll keep",
      "step, from pulls": "switch to git, no reveal",
      "open, from git": "stay on git, reveal, scroll nearest"
    },
    "/raw/notes.md": {
      "tab": null,
      "open, from pulls": "nothing",
      "address, from pulls": "nothing",
      "history, from pulls": "nothing",
      "nav, from pulls": "nothing",
      "tab, from pulls": "nothing",
      "step, from pulls": "nothing"
    }
  },
  "an unknown route": "unknown reveal route: focus",
  "landing": {
    "startup": "address",
    "startup, after a tab landing": "tab",
    "startup, after a history landing": "history",
    "startup, after an open landing": "open",
    "user": "open",
    "user, after a tab landing": "open",
    "user, after a history landing": "open",
    "user, after an open landing": "open",
    "popstate": "history",
    "popstate, after a tab landing": "tab",
    "popstate, after a history landing": "history",
    "popstate, after an open landing": "open"
  },
  "tabs": {
    "steps": [
      {
        "step": "Quick Search or a link opens a file from Files",
        "address": "/view/docs/deep/leaf.md",
        "tab": "files",
        "told": [
          "Files: reveal /view/docs/deep/leaf.md, scroll nearest"
        ]
      },
      {
        "step": "a link opens a pull request: Pulls comes to the front and reveals it",
        "address": "/pull/7",
        "tab": "pulls",
        "told": [
          "Pulls view mounted at current 7",
          "Pulls: #7 revealed",
          "Pulls: current 7"
        ]
      },
      {
        "step": "Quick Search for the pull request shown: no new address, revealed again",
        "address": "/pull/7",
        "tab": "pulls",
        "told": [
          "Pulls: current 7 (again)",
          "Pulls: #7 revealed"
        ]
      },
      {
        "step": "a key skims the Pulls tab's rows: the next is revealed",
        "address": "/pull/8",
        "tab": "pulls",
        "told": [
          "Pulls: current 8",
          "Pulls: #8 revealed"
        ]
      },
      {
        "step": "another tab of #8's page: a step within it, nothing is revealed",
        "address": "/pull/8/files",
        "tab": "pulls",
        "told": [
          "Pulls: current 8"
        ]
      },
      {
        "step": "a changed file of #8 opens from its diff: the list is told, nothing is revealed",
        "address": "/pull/8/files/src/app.txt",
        "tab": "pulls",
        "told": [
          "Pulls: current 8, file src/app.txt"
        ]
      },
      {
        "step": "J walks #8's changed files: the next replaces it, nothing is revealed",
        "address": "/pull/8/files/src/b.txt",
        "tab": "pulls",
        "told": [
          "Pulls: current 8, file src/b.txt"
        ]
      },
      {
        "step": "Quick Search for #8 from one of its files: its page opens, and #8 is revealed again",
        "address": "/pull/8",
        "tab": "pulls",
        "told": [
          "Pulls: current 8",
          "Pulls: current 8 (again)",
          "Pulls: #8 revealed"
        ]
      },
      {
        "step": "a link on the page opens a file: Files comes to the front",
        "address": "/view/src/app.txt",
        "tab": "files",
        "told": [
          "the pane given up",
          "Pulls: current null",
          "Files: reveal /view/src/app.txt, scroll nearest"
        ]
      },
      {
        "step": "a fragment on the file shown is a step: nothing is revealed",
        "address": "/view/src/app.txt",
        "tab": "files",
        "told": [
          "Pulls: current null"
        ]
      },
      {
        "step": "the Pulls tab's button: its destination, with the list as it was",
        "address": "/pull/8",
        "tab": "pulls",
        "told": [
          "the pane given up",
          "Pulls: current 8 (keep scroll)"
        ]
      },
      {
        "step": "Quick Search for the pull request shown after the tab's button: revealed again",
        "address": "/pull/8",
        "tab": "pulls",
        "told": [
          "Pulls: current 8 (again)",
          "Pulls: #8 revealed"
        ]
      },
      {
        "step": "the Files tab's button: its destination, with the tree as it was",
        "address": "/view/src/app.txt",
        "tab": "files",
        "told": [
          "the pane given up",
          "Pulls: current null",
          "Pulls: current null",
          "Files: reveal /view/src/app.txt, scroll keep"
        ]
      },
      {
        "step": "Back to a pull request: Pulls comes to the front and reveals it",
        "address": "/pull/8",
        "tab": "pulls",
        "told": [
          "the pane given up",
          "Pulls: current 8",
          "Pulls: #8 revealed",
          "Pulls: current 8"
        ]
      },
      {
        "step": "Back to a file: Files comes to the front and reveals it",
        "address": "/view/src/app.txt",
        "tab": "files",
        "told": [
          "the pane given up",
          "Pulls: current null",
          "Files: reveal /view/src/app.txt, scroll nearest"
        ]
      },
      {
        "step": "a commit's address: Commits comes to the front; its panel reveals the row",
        "address": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "tab": "git",
        "told": []
      }
    ],
    "tab switches restored the address": 3
  },
  "files tree": [
    {
      "step": "a file three folders down: its folders open",
      "path": "docs/deep/deeper/leaf.md",
      "shown": true,
      "open": [
        "docs",
        "docs/deep",
        "docs/deep/deeper"
      ],
      "selected": [
        "docs/deep/deeper/leaf.md"
      ],
      "scrolled": [
        "docs/deep/deeper/leaf.md"
      ],
      "note": null
    },
    {
      "step": "a tab's landing keeps the tree's place: selected, not scrolled",
      "path": "README.md",
      "shown": true,
      "open": [
        "docs",
        "docs/deep",
        "docs/deep/deeper"
      ],
      "selected": [
        "README.md"
      ],
      "scrolled": [],
      "note": null
    },
    {
      "step": "a file past a long folder's first page: the page holding it is drawn",
      "path": "long/f250.txt",
      "shown": true,
      "open": [
        "docs",
        "docs/deep",
        "docs/deep/deeper",
        "long"
      ],
      "selected": [
        "long/f250.txt"
      ],
      "scrolled": [
        "long/f250.txt"
      ],
      "note": null
    },
    {
      "step": "a path the tree does not hold, with no filter: no row stays selected",
      "path": "gone.txt",
      "shown": false,
      "open": [
        "docs",
        "docs/deep",
        "docs/deep/deeper",
        "long"
      ],
      "selected": [],
      "scrolled": [],
      "note": null
    },
    {
      "step": "back to a listed file",
      "path": "docs/guide.md",
      "shown": true,
      "open": [
        "docs",
        "docs/deep",
        "docs/deep/deeper",
        "long"
      ],
      "selected": [
        "docs/guide.md"
      ],
      "scrolled": [
        "docs/guide.md"
      ],
      "note": null
    },
    {
      "step": "a filter hides its folder: no row stays selected, and the tree says why",
      "path": "src/app.txt",
      "shown": false,
      "open": [],
      "selected": [],
      "scrolled": [],
      "note": "src/app.txt is outside this filter."
    },
    {
      "step": "a file the filter keeps",
      "path": "docs/deep/deeper/leaf.md",
      "shown": true,
      "open": [
        "docs",
        "docs/deep",
        "docs/deep/deeper"
      ],
      "selected": [
        "docs/deep/deeper/leaf.md"
      ],
      "scrolled": [
        "docs/deep/deeper/leaf.md"
      ],
      "note": null
    },
    {
      "step": "a repaint closes the selection's folders: no claim it is outside the filter",
      "path": "docs/deep/deeper/leaf.md",
      "open": [],
      "selected": [],
      "scrolled": [],
      "note": null
    }
  ],
  "pulls list": {
    "steps": [
      {
        "step": "the reader closes Stack #286",
        "stack": "Stack #286 closed",
        "told": []
      },
      {
        "step": "an address names #7, in it: the stack opens, and #7 is revealed",
        "stack": "Stack #286 open",
        "told": [
          "revealed #7"
        ]
      },
      {
        "step": "the reader closes the stack again",
        "stack": "Stack #286 closed",
        "told": []
      },
      {
        "step": "#7 named again, by another tab of its page, one of its files, or a history step: nothing moves",
        "stack": "Stack #286 closed",
        "told": []
      },
      {
        "step": "#7 opened again, by Quick Search: the stack opens, and #7 is revealed",
        "stack": "Stack #286 open",
        "told": [
          "revealed #7"
        ]
      },
      {
        "step": "a tab's landing at #8 keeps the list's place: marked, not revealed",
        "stack": "Stack #286 open",
        "told": []
      },
      {
        "step": "Quick Search for #8 after that landing: revealed, which ends the kept place",
        "stack": "Stack #286 open",
        "told": [
          "revealed #8"
        ]
      },
      {
        "step": "under Open, the list does not hold closed #8, and says so",
        "stack": "Stack #286 open",
        "told": [
          "note: #8 is not listed under Open."
        ]
      },
      {
        "step": "#10 named: listed, so revealed, and the note goes",
        "stack": "Stack #286 open",
        "told": [
          "revealed #10",
          "note gone"
        ]
      },
      {
        "step": "#4000 named under Open: not listed",
        "stack": "Stack #286 open",
        "told": [
          "note: #4000 is not listed under Open."
        ]
      },
      {
        "step": "under All, #4000 is still not listed, and the note names All",
        "stack": "Stack #286 open",
        "told": [
          "note: #4000 is not in this list."
        ]
      },
      {
        "step": "#6 named under All, past the rows read: the list reads on, and reveals it",
        "stack": "Stack #286 open",
        "told": [
          "revealed #6",
          "note gone"
        ]
      }
    ],
    "notes": {
      "Open, read past #8": "#8 is not listed under Open.",
      "Closed, read past #8": "#8 is not listed under Closed.",
      "All, read past #8": "#8 is not in this list.",
      "any list, not read as far as #8": "#8 is not among the pull requests loaded."
    }
  },
  "invariants": {
    "no route moves focus": true,
    "a reveal never leaves another row selected": true,
    "a step within the pull request shown reveals no row, and Quick Search for it does": true
  }
}
? 0
```
