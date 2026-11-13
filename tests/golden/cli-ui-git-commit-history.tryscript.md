---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: Back and Forward across file and commit entries

This session runs the production navigation controller and Git panel over a history of
file and commit entries, and prints what the preview pane shows after each step.
Back onto a commit’s entry used to change the address and leave the file showing.
Now each entry restores its own view, a step within the commit shown loads nothing, and
stepping on before a commit answers leaves the later entry in the pane.
A step taken before the panel is ready ends on the entry the reader stepped to, and a
landing that outlives the panel paints nothing.
An address with a short commit ID says it needs the full lowercase one, a panel that
went away and came back starts over, and a folder that is not a repository has no Git
panel listening.

Switching to Commits names no commit, so it lands on the newest one, the top row.
While the first page of history is on its way the pane keeps what it showed, busy
through the refresh that replaces the walk, and no commit is asked for; then the newest
commit’s address replaces the tab’s entry, and history is asked for once.
A click back to Commits after an older commit lands on the newest again, from the cached
page and detail, with the list scrolled back to its top and focus where it was.
Back steps over each switch to where the reader was, and an entry that names a commit
still shows that commit.
An entry the reader left before history arrived takes nothing when it does, and lands on
the newest when Back reaches it, as a reload onto it does.
An empty history selects nothing and says so; a failed one says so, and the retry that
loads it lands on the newest.
The busy state ends when the commit shows, when a failure is shown, or when the reader
moves on.

The panel’s loading session holds paint callbacks and diff assets independently.
Its initial spinner preserves the connected diff stage, and deferred paint preserves the
ready commit. An older selection’s paint callback preserves the newer selection’s busy
state. A missing commit’s delayed freshness lookup preserves it too.
On the neutral Commits entry the newest row is selected and is the list’s Tab stop, a
scrolled list comes back to its top, and an address that is not the neutral entry
selects nothing. A click leaves focus on the tab, even when focus last parked on the
scroller for a row the landing mounts again.
The tab’s key, `H`, focuses the newest row instead of the older row the reader left,
without scrolling, so `↓` opens the next commit: at once when the row is mounted, or
when the landing reveals it, unless the reader has moved focus by then; the same holds
with Commits in front, and with a page on its way.
A refresh that replaces the focused newest row, or forgets that its focus parked on the
scroller, gives focus to the new one, and focus the reader sends nowhere stays there.
A landing that lost the pane or its address moves neither focus nor the Tab stop, and a
selection whose row a render replaced leaves the Tab stop on the live row.

```console
$ node tests/dom/git-commit-history-session.js
{
  "from a file, through commits": {
    "the page opens on a file": {
      "url": "/view/README.md",
      "pane": "file README.md",
      "owner": "file",
      "navPanel": "files",
      "requests": []
    },
    "selecting a commit replaces the entry": {
      "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "pane": "commit aaaaaaa",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      ]
    },
    "opening a file pushes one": {
      "url": "/view/src/a.py",
      "pane": "file src/a.py",
      "owner": "file",
      "navPanel": "files",
      "requests": []
    },
    "Back shows the commit": {
      "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "pane": "commit aaaaaaa",
      "owner": "git",
      "navPanel": "git",
      "requests": []
    },
    "Forward shows the file": {
      "url": "/view/src/a.py",
      "pane": "file src/a.py",
      "owner": "file",
      "navPanel": "files",
      "requests": []
    },
    "Back shows the commit again": {
      "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "pane": "commit aaaaaaa",
      "owner": "git",
      "navPanel": "git",
      "requests": []
    },
    "another commit replaces the commit's entry": {
      "url": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "pane": "commit bbbbbbb",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      ]
    },
    "Forward from it still shows the file": {
      "url": "/view/src/a.py",
      "pane": "file src/a.py",
      "owner": "file",
      "navPanel": "files",
      "requests": []
    },
    "Back lands on the commit now in that entry": {
      "url": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "pane": "commit bbbbbbb",
      "owner": "git",
      "navPanel": "git",
      "requests": []
    }
  },
  "from a commit's address": {
    "the page opens on the commit": {
      "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/src/a.py",
      "pane": "commit aaaaaaa",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      ]
    },
    "opening a folder pushes an entry": {
      "url": "/view/docs/",
      "pane": "file docs",
      "owner": "file",
      "navPanel": "files",
      "requests": []
    },
    "Back shows the commit, not yet its file": {
      "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/src/a.py",
      "pane": "commit aaaaaaa",
      "owner": "git",
      "navPanel": "git",
      "requests": []
    }
  },
  "a fragment on the commit shown": {
    "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "pane": "commit aaaaaaa",
    "owner": "git",
    "navPanel": "git",
    "requests": []
  },
  "stepping on while the panel catches up": {
    "url": "/view/src/a.py",
    "pane": "file src/a.py",
    "owner": "file",
    "navPanel": "files",
    "requests": []
  },
  "stepping on while the commit loads": {
    "url": "/view/src/a.py",
    "pane": "file src/a.py",
    "owner": "file",
    "navPanel": "files",
    "requests": [
      "GET /api/git/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    ]
  },
  "an address the repository cannot answer": {
    "absent": {
      "url": "/commit/0000000000000000000000000000000000000000",
      "pane": "Commit not found: This commit is not in the repository.",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/0000000000000000000000000000000000000000"
      ]
    },
    "opened": {
      "url": "/commit/aaaaaaa",
      "pane": "Full commit ID needed: A commit’s address uses its full 40- or 64-character lowercase ID, not “aaaaaaa”.",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/aaaaaaa"
      ]
    },
    "landed": {
      "url": "/commit/aaaaaaa",
      "pane": "Full commit ID needed: A commit’s address uses its full 40- or 64-character lowercase ID, not “aaaaaaa”.",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/aaaaaaa"
      ]
    },
    "unreachable": {
      "url": "/commit/aaaaaaa",
      "pane": "Full commit ID needed: A commit’s address uses its full 40- or 64-character lowercase ID, not “aaaaaaa”.",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/aaaaaaa"
      ]
    },
    "uppercase": {
      "url": "/commit/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
      "pane": "Full commit ID needed: A commit’s address uses its full 40- or 64-character lowercase ID, not “AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA”.",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
      ]
    }
  },
  "stepping before the panel is ready": {
    "waiting": {
      "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "pane": "file src/a.py",
      "owner": "file",
      "navPanel": "files",
      "requests": []
    },
    "ready": {
      "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "pane": "commit aaaaaaa",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      ]
    },
    "moved": {
      "url": "/view/src/a.py",
      "pane": "file src/a.py",
      "owner": "file",
      "navPanel": "files",
      "requests": []
    }
  },
  "a landing when the root stopped being a repository": {
    "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "pane": "file src/a.py",
    "owner": "file",
    "navPanel": "files",
    "requests": []
  },
  "a landing when the repository gate failed once": {
    "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "pane": "file src/a.py",
    "owner": "file",
    "navPanel": "files",
    "requests": []
  },
  "a panel that came back starts over": {
    "selection": {
      "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "pane": "commit aaaaaaa",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      ]
    },
    "refusal": {
      "url": "/commit/aaaaaaa",
      "pane": "Could not load this commit.",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/aaaaaaa"
      ]
    }
  },
  "a folder that is not a repository": {
    "url": "/view/README.md",
    "pane": "file README.md",
    "owner": "file",
    "navPanel": "files",
    "requests": []
  },
  "switching to Commits": {
    "the page opens on a file": {
      "url": "/view/README.md",
      "pane": "file README.md",
      "owner": "file",
      "navPanel": "files",
      "requests": []
    },
    "Commits, while the first page of history loads": {
      "url": "/view/",
      "pane": "file README.md",
      "owner": "git",
      "navPanel": "git",
      "requests": [],
      "entries": 2,
      "historyReads": 1,
      "focusMoves": 0,
      "busy": true,
      "scrollTop": 0
    },
    "the newest commit, once history arrives": {
      "url": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "pane": "commit bbbbbbb",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      ],
      "entries": 2,
      "historyReads": 1,
      "focusMoves": 0,
      "busy": false,
      "scrollTop": 0
    },
    "an older commit": {
      "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "pane": "commit aaaaaaa",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      ]
    },
    "a file": {
      "url": "/view/src/a.py",
      "pane": "file src/a.py",
      "owner": "file",
      "navPanel": "files",
      "requests": []
    },
    "Commits again": {
      "url": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "pane": "commit bbbbbbb",
      "owner": "git",
      "navPanel": "git",
      "requests": [],
      "entries": 4,
      "historyReads": 1,
      "focusMoves": 0,
      "busy": false,
      "scrollTop": 0
    },
    "Back": {
      "url": "/view/src/a.py",
      "pane": "file src/a.py",
      "owner": "file",
      "navPanel": "files",
      "requests": []
    },
    "Back onto the older commit's entry": {
      "url": "/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "pane": "commit aaaaaaa",
      "owner": "git",
      "navPanel": "git",
      "requests": []
    }
  },
  "an entry left before history arrived": {
    "movedOn": {
      "url": "/view/src/a.py",
      "pane": "file src/a.py",
      "owner": "file",
      "navPanel": "files",
      "requests": []
    },
    "back": {
      "url": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "pane": "commit bbbbbbb",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      ],
      "entries": 3,
      "historyReads": 1,
      "focusMoves": 0,
      "busy": false
    }
  },
  "a reload onto the tab's entry": {
    "url": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "pane": "commit bbbbbbb",
    "owner": "git",
    "navPanel": "git",
    "requests": [
      "GET /api/git/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    ]
  },
  "an empty or failed history": {
    "empty": {
      "url": "/view/",
      "pane": "No commits yet.",
      "owner": "git",
      "navPanel": "git",
      "requests": []
    },
    "failed": {
      "url": "/view/",
      "pane": "Could not load the commit history.",
      "owner": "git",
      "navPanel": "git",
      "requests": [],
      "busy": false
    },
    "retried": {
      "url": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "pane": "commit bbbbbbb",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      ]
    }
  }
}
? 0
```

```console
$ node tests/dom/git-panel-behavior.js
OK git panel behavior
commit loading session {"paint":{"readyConnected":true,"loading":false},"assets":{"stageConnected":true,"spinner":true},"crossing":{"newerBusyAfterOlderPaint":true},"missing":{"newerBusyAfterMissing":true}}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
