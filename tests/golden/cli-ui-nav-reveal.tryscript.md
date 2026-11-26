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
focus. `files tree` lifts `app.js`’s tree reveal and its page mounting verbatim over a
stand-in tree whose renderer pages as production’s does, 200 rows and then a “more” row:
closed folders open, and in a folder of 1,400 files only the page that holds the row is
drawn, with the pages before and after it behind rows of their own, which draw in order
where they are. One above the reader’s row grows up and gives focus to the row nearest
it; one below grows down and gives focus to its first row, after a second reveal in the
folder too. A file that arrives while the page is open counts in every one of the
folder’s “more” rows, and one that sorts last goes last.
A reveal that cannot show its row leaves no other row selected, and the tree says a file
is outside the filter only when the filter is what hides it.
A landing whose folder is still opening scrolls its row once the folder’s travel ends,
not before, and only while the address still names it and the folder is open, to the row
drawn in its place if it was drawn again; an endless animation holds no scroll.
`pulls list` runs the Pulls tab’s controller over the recorded lists and stack snapshot:
an address naming a pull request in a closed stack opens the stack, the same pull
request named again moves nothing unless it was opened again, which reveals it and ends
a tab landing’s kept place, and under All the list reads on for one past the rows it has
read. A pull request Open or Closed leaves out moves the list to a filter that draws it,
which reveals it, when a navigation names it; when the reader picks the filter, the list
says nothing of it. The catalog’s one-row lookups say where the pull request is.
Only one the list still cannot show is named under the band: one the catalog, read to
its end, lacks, or one further down than the list draws.
The lists that run past what the panel draws are in the next section.

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
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 1200 more (1400 total)"
      ]
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
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 1200 more (1400 total)"
      ]
    },
    {
      "step": "a file in a long folder's second page: that page is drawn, the rest stays behind its row",
      "path": "long/f0250.txt",
      "shown": true,
      "open": [
        "docs",
        "docs/deep",
        "docs/deep/deeper",
        "long"
      ],
      "selected": [
        "long/f0250.txt"
      ],
      "scrolled": [
        "long/f0250.txt"
      ],
      "note": null,
      "long folder": [
        "f0000–f0399",
        "Show 1000 more (1400 total)"
      ]
    },
    {
      "step": "a file in its fifth page: only that page is drawn, between rows for the pages around it",
      "path": "long/f0905.txt",
      "shown": true,
      "open": [
        "docs",
        "docs/deep",
        "docs/deep/deeper",
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [
        "long/f0905.txt"
      ],
      "note": null,
      "long folder": [
        "f0000–f0399",
        "Show 400 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "the row above the revealed page draws the page before it there, and keeps focus nearby",
      "path": "long/f0905.txt",
      "open": [
        "docs",
        "docs/deep",
        "docs/deep/deeper",
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0599",
        "Show 200 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ],
      "focus goes to": "Show 200 more (1400 total)"
    },
    {
      "step": "again: the folder reads in order up to the revealed page",
      "path": "long/f0905.txt",
      "open": [
        "docs",
        "docs/deep",
        "docs/deep/deeper",
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0999",
        "Show 400 more (1400 total)"
      ],
      "focus goes to": "long/f0799.txt"
    },
    {
      "step": "the row that ends the folder draws down from there, as before",
      "path": "long/f0905.txt",
      "open": [
        "docs",
        "docs/deep",
        "docs/deep/deeper",
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f1199",
        "Show 200 more (1400 total)"
      ],
      "focus goes to": "long/f1000.txt"
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
      "note": null,
      "long folder": [
        "f0000–f1199",
        "Show 200 more (1400 total)"
      ]
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
      "note": null,
      "long folder": [
        "f0000–f1199",
        "Show 200 more (1400 total)"
      ]
    },
    {
      "step": "a long folder again, a file in its fifth page",
      "path": "long/f0905.txt",
      "shown": true,
      "open": [
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [
        "long/f0905.txt"
      ],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 600 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "then one in its third: only its page is drawn, above the first's",
      "path": "long/f0405.txt",
      "shown": true,
      "open": [
        "long"
      ],
      "selected": [
        "long/f0405.txt"
      ],
      "scrolled": [
        "long/f0405.txt"
      ],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 200 more (1400 total)",
        "f0400–f0599",
        "Show 200 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "the row below the reader's, pressed: its page grows down, and focus goes to its first row",
      "path": "long/f0405.txt",
      "open": [
        "long"
      ],
      "selected": [
        "long/f0405.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 200 more (1400 total)",
        "f0400–f0999",
        "Show 400 more (1400 total)"
      ],
      "focus goes to": "long/f0600.txt"
    },
    {
      "step": "a file arrives within a drawn page: each 'more' row counts it",
      "path": "long/f0405.txt",
      "open": [
        "long"
      ],
      "selected": [
        "long/f0405.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 200 more (1401 total)",
        "f0400–f0650",
        "f0650a",
        "f0651–f0999",
        "Show 400 more (1401 total)"
      ]
    },
    {
      "step": "the row above the reader's, pressed: the rows it draws count the arrival, and focus goes to the row nearest the reader's",
      "path": "long/f0405.txt",
      "open": [
        "long"
      ],
      "selected": [
        "long/f0405.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0650",
        "f0650a",
        "f0651–f0999",
        "Show 400 more (1401 total)"
      ],
      "focus goes to": "long/f0399.txt",
      "totals the rows give": [
        "1401"
      ]
    },
    {
      "step": "a file in the folder's last page",
      "path": "long/f1350.txt",
      "shown": true,
      "open": [
        "long"
      ],
      "selected": [
        "long/f1350.txt"
      ],
      "scrolled": [
        "long/f1350.txt"
      ],
      "note": null,
      "long folder": [
        "f0000–f0650",
        "f0650a",
        "f0651–f0999",
        "Show 200 more (1401 total)",
        "f1200–f1399"
      ]
    },
    {
      "step": "a file that sorts last arrives: it goes last, after the page drawn",
      "path": "long/f1350.txt",
      "open": [
        "long"
      ],
      "selected": [
        "long/f1350.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0650",
        "f0650a",
        "f0651–f0999",
        "Show 200 more (1402 total)",
        "f1200–f1399",
        "zzz"
      ]
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
    },
    {
      "step": "a landing in the long folder's fifth page, while the folder opens: selected, not yet scrolled",
      "path": "long/f0905.txt",
      "shown": true,
      "open": [
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 600 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "its travel ends: the row is scrolled into view",
      "path": "long/f0905.txt",
      "open": [
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [
        "long/f0905.txt"
      ],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 600 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "a landing, then another file revealed during its travel: not yet scrolled",
      "path": "long/f0905.txt",
      "shown": true,
      "open": [
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 600 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "the other file's reveal scrolls at once",
      "path": "README.md",
      "shown": true,
      "open": [
        "long"
      ],
      "selected": [
        "README.md"
      ],
      "scrolled": [
        "README.md"
      ],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 600 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "the travel ends: the landing no longer stands, so its row is not scrolled",
      "path": "README.md",
      "open": [
        "long"
      ],
      "selected": [
        "README.md"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 600 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "a landing, then its folder closed during the travel: not yet scrolled",
      "path": "long/f0905.txt",
      "shown": true,
      "open": [
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 600 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "the travel ends: the folder is closed, so its row is not scrolled",
      "path": "long/f0905.txt",
      "open": [],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 600 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "a landing, then its row drawn again during the travel: not yet scrolled",
      "path": "long/f0905.txt",
      "shown": true,
      "open": [
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 600 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "the travel ends: the row drawn in its place is scrolled into view",
      "path": "long/f0905.txt",
      "open": [
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [
        "long/f0905.txt"
      ],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 600 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
    },
    {
      "step": "an endless animation on the folder's body: the reveal scrolls at once",
      "path": "long/f0905.txt",
      "open": [
        "long"
      ],
      "selected": [
        "long/f0905.txt"
      ],
      "scrolled": [
        "long/f0905.txt"
      ],
      "note": null,
      "long folder": [
        "f0000–f0199",
        "Show 600 more (1400 total)",
        "f0800–f0999",
        "Show 400 more (1400 total)"
      ]
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
        "step": "the reader picks Open, which leaves out closed #8: the list says nothing of it",
        "stack": "Stack #286 open",
        "told": [
          "filter open"
        ]
      },
      {
        "step": "Quick Search for #8 again: Open leaves it out, so the list goes to All and reveals it",
        "stack": "Stack #286 open",
        "told": [
          "filter all",
          "revealed #8"
        ]
      },
      {
        "step": "the reader picks Open",
        "stack": "Stack #286 open",
        "told": [
          "filter open"
        ]
      },
      {
        "step": "#10 named: listed, so revealed",
        "stack": "Stack #286 open",
        "told": [
          "revealed #10"
        ]
      },
      {
        "step": "the reader picks Closed while open #10 is shown: Closed leaves it out, and the list says nothing of it",
        "stack": "Stack #286 open",
        "told": [
          "filter closed"
        ]
      },
      {
        "step": "#8 named under Closed: listed, so revealed",
        "stack": "Stack #286 open",
        "told": [
          "revealed #8"
        ]
      },
      {
        "step": "open #10 named under Closed, by Back: the list goes to All and reveals it",
        "stack": "Stack #286 open",
        "told": [
          "filter all",
          "revealed #10"
        ]
      },
      {
        "step": "the reader picks Open",
        "stack": "Stack #286 open",
        "told": [
          "filter open",
          "revealed #10"
        ]
      },
      {
        "step": "#4000 named under Open: the catalog, read in full, lacks it, so the list stays and says so",
        "stack": "Stack #286 open",
        "told": [
          "note: #4000 is not in this list."
        ]
      },
      {
        "step": "the reader picks All: the filter is theirs, and the note goes",
        "stack": "Stack #286 open",
        "told": [
          "note gone",
          "filter all"
        ]
      },
      {
        "step": "#6 named under All, past the rows read: the list reads on, and reveals it",
        "stack": "Stack #286 open",
        "told": [
          "revealed #6"
        ]
      }
    ],
    "notes": {
      "in the catalog, further down than the list draws": "#8 is not among the pull requests loaded.",
      "not in the catalog, which has been read in full": "#8 is not in this list."
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

## Beyond the Rows Read

The part `pulls-depth` serves lists longer than the panel draws, in the route’s windows,
and the catalog’s one-row lookups.
Closed reads on for one past its first window; an open pull request among All’s first
500 rows moves the list to All, and an older one to Open, which draws it, from All too;
and a closed one further down than Closed draws stays, and is noted, as it is once the
list has moved to Closed from All; the pages the reader scrolls in keep the note, with
no flicker, until the page that brings the row, which reveals it.
`crawling` names a pull request the catalog has not read from GitHub yet: the list stays
and says nothing, and once the catalog has it, the next poll reveals it under Closed.
One opened since the catalog’s last read is noted until a poll brings its row, which
reveals it; under the other filter, the list asks again only after a poll says the
catalog has read more than the lookup that lacked it saw, though the read of the newest
row saw it read in, and then goes to All and reveals it.
A catalog that starts again drops what the old one lacked: the note goes, and comes back
only once the new catalog, read to its end, lacks it too.
`failing` has the Closed list fail, which the catalog’s lookups do not need, then the
lookups fail, which leaves the list where it is until the next poll asks again, and then
the list the navigation moved to fails its first read, so its next poll reveals the row.
`answers that come late` holds the lookups until a newer navigation, a filter the reader
picks, or hiding the panel has let them go: their answers are ignored, and a panel shown
again asks again. `focus` moves the list for a pull request while focus is on a row, as
Control-N does: when its read arrives, the row takes focus if focus is still in the list
or on no element, where the move left it, and not if the reader moved it elsewhere.
`a number the route refuses` names the largest number a pull request may have, which the
route refuses as the start of a read: the newest row says the catalog lacks it, and no
poll asks again.

```console
$ node tests/dom/nav-reveal-session.js pulls-depth
{
  "beyond the rows read": {
    "past what the list draws": [
      {
        "step": "the reader picks Closed, and a link names closed #2700 before its rows arrive: Closed holds it past its first window, so the list stays, reads on, and reveals it",
        "read": [
          "closed",
          "lookup: #2700 or the next older",
          "lookup: the newest",
          "closed after #2801",
          "closed after #2701",
          "closed after #2601",
          "closed after #2501"
        ],
        "told": [
          "filter closed",
          "revealed #2700"
        ]
      },
      {
        "step": "open #2950 named under Closed: the catalog says it is open and among All's first 500, so the list goes to All and reveals it",
        "read": [
          "lookup: #2950 or the next older",
          "lookup: the newest",
          "all",
          "all after #2901",
          "all after #2801",
          "all after #2701",
          "all after #2601"
        ],
        "told": [
          "filter all",
          "revealed #2950"
        ]
      },
      {
        "step": "the reader picks Closed",
        "read": [
          "closed"
        ],
        "told": [
          "filter closed"
        ]
      },
      {
        "step": "open #1000 named under Closed: All's 500 rows do not reach it, so the list goes to Open, which draws it, and reveals it",
        "read": [
          "lookup: #1000 or the next older",
          "lookup: the newest",
          "open"
        ],
        "told": [
          "filter open",
          "revealed #1000"
        ]
      },
      {
        "step": "the reader picks Closed",
        "read": [
          "closed"
        ],
        "told": [
          "filter closed"
        ]
      },
      {
        "step": "closed #1500 named under Closed: it is further down than Closed draws, so the list stays and says so",
        "read": [
          "lookup: #1500 or the next older",
          "lookup: the newest"
        ],
        "told": [
          "note: #1500 is not among the pull requests loaded."
        ]
      },
      {
        "step": "the reader picks Open: the filter is theirs, and the note goes",
        "read": [
          "open"
        ],
        "told": [
          "note gone",
          "filter open"
        ]
      },
      {
        "step": "the reader picks Closed, and a link names open #2950: the list goes to All and reveals it",
        "read": [
          "closed",
          "lookup: #2950 or the next older",
          "lookup: the newest",
          "all"
        ],
        "told": [
          "filter closed",
          "filter all",
          "revealed #2950"
        ]
      },
      {
        "step": "a link from #2950 names open #1000: All's 500 rows do not reach it, so the list goes on to Open, which draws it, and reveals it",
        "read": [
          "lookup: #1000 or the next older",
          "lookup: the newest",
          "open"
        ],
        "told": [
          "filter open",
          "revealed #1000"
        ]
      },
      {
        "step": "the reader picks All",
        "read": [
          "all"
        ],
        "told": [
          "filter all"
        ]
      },
      {
        "step": "closed #1500 named under All: All's rows do not reach it, so the list goes to Closed, which reaches furthest, and says it is further down than Closed draws too",
        "read": [
          "lookup: #1500 or the next older",
          "lookup: the newest",
          "closed"
        ],
        "told": [
          "note: #1500 is not among the pull requests loaded.",
          "filter closed"
        ]
      },
      {
        "step": "the reader scrolls to the list's end: Closed reads a page of 100 more, and the note stays as it was",
        "read": [
          "closed after #2401"
        ],
        "told": []
      },
      {
        "step": "the reader scrolls on, nine pages more: the note stays until the page that brings #1500, which reveals it, and then goes",
        "read": [
          "closed after #2301",
          "closed after #2201",
          "closed after #2101",
          "closed after #2001",
          "closed after #1901",
          "closed after #1801",
          "closed after #1701",
          "closed after #1601",
          "closed after #1501"
        ],
        "told": [
          "note gone",
          "revealed #1500"
        ]
      }
    ],
    "crawling": [
      {
        "step": "a link names closed #2700 while the catalog has read 200 of 2,001 from GitHub: where it is is not known yet, so the list stays and says nothing",
        "read": [
          "lookup: #2700 or the next older",
          "lookup: the newest"
        ],
        "told": []
      },
      {
        "step": "the catalog reads to its end, and time passes: the next poll finds #2700 closed, so the list stays, reads on, and reveals it",
        "read": [
          "closed",
          "lookup: #2700 or the next older",
          "lookup: the newest",
          "closed after #2801",
          "closed after #2701",
          "closed after #2601",
          "closed after #2501"
        ],
        "told": [
          "revealed #2700"
        ]
      },
      {
        "step": "a link names open #2995, opened since the catalog's last read: the catalog, read to its end, lacks it, so the list says so",
        "read": [
          "lookup: #2995 or the next older",
          "lookup: the newest"
        ],
        "told": [
          "note: #2995 is not in this list."
        ]
      },
      {
        "step": "the catalog reads it, and time passes: the next poll brings its row, so the note goes and the row is revealed",
        "read": [
          "open",
          "open after #2901"
        ],
        "told": [
          "note gone",
          "revealed #2995"
        ]
      },
      {
        "step": "a link names open #2995 under Closed, opened since the catalog's last read: the catalog, read to its end, lacks it, so the list stays and says so",
        "read": [
          "lookup: #2995 or the next older",
          "lookup: the newest"
        ],
        "told": [
          "note: #2995 is not in this list."
        ]
      },
      {
        "step": "time passes, and the catalog has read nothing new: the next poll does not ask again",
        "read": [
          "closed"
        ],
        "told": []
      },
      {
        "step": "the catalog reads #2995, and time passes: Closed's next poll says the catalog has read more, so the list asks again, goes to All, and reveals it",
        "read": [
          "closed",
          "lookup: #2995 or the next older",
          "lookup: the newest",
          "all",
          "all after #2901",
          "all after #2801",
          "all after #2701",
          "all after #2601"
        ],
        "told": [
          "note gone",
          "filter all",
          "revealed #2995"
        ]
      },
      {
        "step": "a link names open #2995 under Closed as the catalog reads it in: the lookup of #2995 answers before, and that of the newest row after, so the catalog as the first saw it lacks #2995, and the list says so",
        "read": [
          "lookup: #2995 or the next older",
          "lookup: the newest"
        ],
        "told": [
          "note: #2995 is not in this list."
        ]
      },
      {
        "step": "time passes: Closed's next poll says the catalog has read more than the lookup of #2995 saw, so the list asks again, goes to All, and reveals it",
        "read": [
          "closed",
          "lookup: #2995 or the next older",
          "lookup: the newest",
          "all",
          "all after #2901",
          "all after #2801",
          "all after #2701",
          "all after #2601"
        ],
        "told": [
          "note gone",
          "filter all",
          "revealed #2995"
        ]
      },
      {
        "step": "a link names #4000 under Closed: the catalog, read to its end, lacks it, so the list says so",
        "read": [
          "lookup: #4000 or the next older",
          "lookup: the newest"
        ],
        "told": [
          "note: #4000 is not in this list."
        ]
      },
      {
        "step": "the catalog starts again, as for a new reader, and has read 200 so far; time passes: what the old catalog lacked is not known of the new one yet, so the note goes and the list says nothing",
        "read": [
          "closed",
          "lookup: #4000 or the next older",
          "lookup: the newest"
        ],
        "told": [
          "note gone"
        ]
      },
      {
        "step": "the catalog reads to its end, and time passes: it lacks #4000 too, so the list says so again",
        "read": [
          "closed",
          "lookup: #4000 or the next older",
          "lookup: the newest",
          "closed after #2801",
          "closed after #2701",
          "closed after #2601",
          "closed after #2501"
        ],
        "told": [
          "note: #4000 is not in this list."
        ]
      }
    ],
    "failing": [
      {
        "step": "the Closed list answers HTTP 500, and a link names open #2950: the catalog still says where it is, so the list goes to All and reveals it",
        "read": [
          "lookup: #2950 or the next older",
          "lookup: the newest",
          "all",
          "all after #2901",
          "all after #2801",
          "all after #2701",
          "all after #2601"
        ],
        "told": [
          "filter all",
          "revealed #2950"
        ]
      },
      {
        "step": "the reader picks Closed, which answers again",
        "read": [
          "closed",
          "closed after #2801",
          "closed after #2701",
          "closed after #2601",
          "closed after #2501"
        ],
        "told": [
          "filter closed"
        ]
      },
      {
        "step": "the catalog's lookups fail as a link names open #2940: where it is is not known, so the list stays and says nothing",
        "read": [
          "lookup: #2940 or the next older",
          "lookup: the newest"
        ],
        "told": []
      },
      {
        "step": "the lookups answer again, and time passes: the next poll asks again, so the list goes to All and reveals #2940",
        "read": [
          "closed",
          "lookup: #2940 or the next older",
          "lookup: the newest",
          "all"
        ],
        "told": [
          "filter all",
          "revealed #2940"
        ]
      },
      {
        "step": "open #2950 named under Closed while All answers HTTP 500: the list goes to All, whose first read fails, so nothing is revealed and nothing noted",
        "read": [
          "lookup: #2950 or the next older",
          "lookup: the newest",
          "all"
        ],
        "told": [
          "filter all"
        ]
      },
      {
        "step": "All answers again, and time passes: the next poll brings #2950's row, and reveals it",
        "read": [
          "all",
          "all after #2901",
          "all after #2801",
          "all after #2701",
          "all after #2601"
        ],
        "told": [
          "revealed #2950"
        ]
      },
      {
        "step": "time passes again: #2950 is revealed once, not at every poll",
        "read": [
          "all"
        ],
        "told": []
      }
    ],
    "answers that come late": [
      {
        "step": "a link names open #1000 under Closed while the catalog is slow to answer: the list waits and says nothing",
        "read": [
          "lookup: #1000 or the next older",
          "lookup: the newest"
        ],
        "told": []
      },
      {
        "step": "a second link names open #2950 before that answer: the first lookup is let go, and the second waits",
        "read": [
          "lookup: #2950 or the next older",
          "lookup: the newest"
        ],
        "told": [],
        "let go": [
          "lookup: #1000 or the next older",
          "lookup: the newest"
        ]
      },
      {
        "step": "both answers come: the one for #1000 is ignored, and #2950 is among All's first 500, so the list goes to All and reveals it",
        "read": [
          "all",
          "all after #2901",
          "all after #2801",
          "all after #2701",
          "all after #2601"
        ],
        "told": [
          "filter all",
          "revealed #2950"
        ]
      },
      {
        "step": "the reader picks Closed, and a link names open #1000 while the catalog is slow again",
        "read": [
          "closed",
          "lookup: #1000 or the next older",
          "lookup: the newest"
        ],
        "told": [
          "filter closed"
        ]
      },
      {
        "step": "the reader picks All before the answer: the lookup is let go, and the filter is theirs",
        "read": [
          "all"
        ],
        "told": [
          "filter all"
        ],
        "let go": [
          "lookup: #1000 or the next older",
          "lookup: the newest"
        ]
      },
      {
        "step": "the answer comes: it is ignored, so the list stays under All and says nothing",
        "read": [],
        "told": []
      },
      {
        "step": "the reader picks Closed, and a link names open #2950 while the catalog is slow",
        "read": [
          "closed",
          "lookup: #2950 or the next older",
          "lookup: the newest"
        ],
        "told": [
          "filter closed"
        ]
      },
      {
        "step": "the panel is hidden before the answer: its reads end, the lookups among them",
        "read": [],
        "told": [],
        "let go": [
          "lookup: #2950 or the next older",
          "lookup: the newest"
        ]
      },
      {
        "step": "the answer comes while the panel is hidden: it is ignored",
        "read": [],
        "told": []
      },
      {
        "step": "the panel is shown again: its next poll asks again, so the list goes to All and reveals #2950",
        "read": [
          "closed",
          "lookup: #2950 or the next older",
          "lookup: the newest",
          "all"
        ],
        "told": [
          "filter all",
          "revealed #2950"
        ]
      }
    ],
    "focus": [
      {
        "step": "with focus on a row, open #2950 named under Closed, as Control-N names it: the list goes to All, whose rows are slow",
        "read": [
          "lookup: #2950 or the next older",
          "lookup: the newest",
          "all"
        ],
        "told": [
          "filter all"
        ]
      },
      {
        "step": "the reader moves focus out of the list, and All's rows come: #2950 is revealed, and focus stays where the reader put it",
        "read": [
          "all after #2901",
          "all after #2801",
          "all after #2701",
          "all after #2601"
        ],
        "told": [
          "revealed #2950"
        ]
      },
      {
        "step": "the reader picks Closed, and puts focus on a row",
        "read": [
          "closed"
        ],
        "told": [
          "filter closed"
        ]
      },
      {
        "step": "open #2940 named, as Control-N names it: the list goes to All, whose rows are slow again",
        "read": [
          "lookup: #2940 or the next older",
          "lookup: the newest",
          "all"
        ],
        "told": [
          "filter all"
        ]
      },
      {
        "step": "All's rows come with focus where the move left it, on no element: #2940 is revealed, and takes focus",
        "read": [],
        "told": [
          "revealed #2940",
          "focused #2940"
        ]
      }
    ],
    "a number the route refuses": [
      {
        "step": "a link names #9999999999, the largest number a pull request may have: the route refuses a read from above it, and the newest pull request is older, so the catalog lacks it and the list says so",
        "read": [
          "lookup: #9999999999 or the next older",
          "lookup: the newest"
        ],
        "told": [
          "note: #9999999999 is not in this list."
        ]
      },
      {
        "step": "time passes: the next poll does not ask again",
        "read": [
          "closed"
        ],
        "told": []
      }
    ]
  }
}
? 0
```

## A Link’s Address

The part `links` opens, by a plain click on a link in a text, an address that Pulls or
Commits holds, through the SDK’s `navigation.openRoute` (`static/navigation.js`) and the
tab controller’s `openRoute` (`static/main-tabs.js`), both loaded whole.
Each open pushes one entry, the link’s own address, and lands as a tab’s destination
lands: a switch of tab gives up the pane, the pane shows the address, its tab comes to
the front, and its panel reveals the item.
A commit is the Commits panel’s to select, and a pull request’s page that holds the pane
writes its place into its own entry first.
Another tab of the pull request shown reveals no row, and another pull request reveals
its own. A link to the address shown, the same stack’s page, the list, or a changed file
of a pull request, opens it again where it is: it pushes no entry and the pane shows
nothing anew, so the reader keeps their place, and the panel reveals the item again.
An address the shell cannot show in place answers false and moves, writes, and tells
nothing, so the browser follows the link: before the shell tools have loaded, a commit
before Git discovery has registered Commits, a file’s address (`navigation.open` opens
those), another origin, an address the pull-request routes do not read, and one no tab
holds.

```console
$ node tests/dom/nav-reveal-session.js links
{
  "a link's address": {
    "opened": [
      {
        "step": "a Markdown file links a commit: Commits comes to the front and its panel selects it",
        "href": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "address": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "tab": "git",
        "told": [
          "the pane given up",
          "the pane shows /commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
          "Commits: selects bbbbbbb and reveals its row"
        ]
      },
      {
        "step": "the commit's message links another commit: Commits stays, and its panel claims the pane",
        "href": "/commit/cccccccccccccccccccccccccccccccccccccccc",
        "address": "/commit/cccccccccccccccccccccccccccccccccccccccc",
        "tab": "git",
        "told": [
          "the pane shows /commit/cccccccccccccccccccccccccccccccccccccccc",
          "Commits: selects ccccccc and reveals its row"
        ]
      },
      {
        "step": "the message links a pull request: Pulls comes to the front and reveals it",
        "href": "/pull/8",
        "address": "/pull/8",
        "tab": "pulls",
        "told": [
          "the pane given up",
          "the pane shows /pull/8",
          "Pulls view mounted at current 8",
          "Pulls: #8 revealed",
          "Pulls: current 8"
        ]
      },
      {
        "step": "a document drawn in #8's Changes links #8's Changes: a step within it, nothing revealed",
        "href": "/pull/8/files",
        "address": "/pull/8/files",
        "tab": "pulls",
        "told": [
          "#8's page writes its place into its entry",
          "the pane shows /pull/8/files",
          "Pulls: current 8"
        ]
      },
      {
        "step": "the same document links #7: its row is revealed",
        "href": "/pull/7",
        "address": "/pull/7",
        "tab": "pulls",
        "told": [
          "#8's page writes its place into its entry",
          "the pane shows /pull/7",
          "Pulls: #7 revealed",
          "Pulls: current 7"
        ]
      },
      {
        "step": "#7's description links a commit: its page writes its place, and Commits comes to the front",
        "href": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb#diff",
        "address": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "tab": "git",
        "told": [
          "#7's page writes its place into its entry",
          "the pane given up",
          "the pane shows /commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
          "Commits: selects bbbbbbb and reveals its row",
          "Pulls: current null"
        ]
      },
      {
        "step": "the commit's message links the list: Pulls comes to the front, and the pane shows it",
        "href": "/pulls",
        "address": "/pulls",
        "tab": "pulls",
        "told": [
          "the pane given up",
          "the pane shows /pulls",
          "Pulls: current null"
        ]
      },
      {
        "step": "a link opens a stack's page",
        "href": "/stack/3",
        "address": "/stack/3",
        "tab": "pulls",
        "told": [
          "the pane shows /stack/3",
          "Pulls: current null"
        ]
      },
      {
        "step": "a link to the stack's page shown opens it again, pushing nothing",
        "href": "/stack/3",
        "address": "/stack/3",
        "tab": "pulls",
        "told": [
          "Pulls: current null (again)"
        ]
      },
      {
        "step": "a link opens the list",
        "href": "/pulls",
        "address": "/pulls",
        "tab": "pulls",
        "told": [
          "the pane shows /pulls",
          "Pulls: current null"
        ]
      },
      {
        "step": "a link to the list shown opens it again, pushing nothing",
        "href": "/pulls",
        "address": "/pulls",
        "tab": "pulls",
        "told": [
          "Pulls: current null (again)"
        ]
      },
      {
        "step": "a link opens a changed file of #8",
        "href": "/pull/8/files/docs/a%20b.md",
        "address": "/pull/8/files/docs/a%20b.md",
        "tab": "pulls",
        "told": [
          "the pane shows /pull/8/files/docs/a%20b.md",
          "Pulls: #8 revealed",
          "Pulls: current 8, file docs/a b.md"
        ]
      },
      {
        "step": "a link to the changed file shown opens it again, pushing nothing",
        "href": "/pull/8/files/docs/a%20b.md",
        "address": "/pull/8/files/docs/a%20b.md",
        "tab": "pulls",
        "told": [
          "Pulls: #8 revealed",
          "Pulls: current 8, file docs/a b.md (again)"
        ]
      }
    ],
    "the browser follows": [
      {
        "link": "the list, before the shell tools have loaded: no controller opens it",
        "href": "/pulls"
      },
      {
        "link": "a commit, before Git discovery has registered the Commits tab",
        "href": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      },
      {
        "link": "a file's address, which navigation.open opens",
        "href": "/view/docs/guide.md"
      },
      {
        "link": "the served root's",
        "href": "/view/"
      },
      {
        "link": "an address on another origin",
        "href": "https://example.com/pulls"
      },
      {
        "link": "a protocol-relative address, on another origin",
        "href": "//example.com/pull/8"
      },
      {
        "link": "a backslash the URL parser reads as a second slash",
        "href": "/\\example.com/pulls"
      },
      {
        "link": "GitHub's page that opens a pull request, which the routes do not read",
        "href": "/pull/new/topic"
      },
      {
        "link": "a pull request numbered 0",
        "href": "/pull/0"
      },
      {
        "link": "a tab a stack's page does not have",
        "href": "/stack/3/checks"
      },
      {
        "link": "a commit's address with no revision",
        "href": "/commit/"
      },
      {
        "link": "an address no tab holds",
        "href": "/raw/notes.md"
      },
      {
        "link": "no URL at all",
        "href": "http://["
      }
    ]
  },
  "invariants": {
    "an open pushes one entry, the link's own address, and none for the address shown": true,
    "an address the shell cannot open in place moves, writes, and tells nothing": true,
    "no link moves focus": true
  }
}
? 0
```
