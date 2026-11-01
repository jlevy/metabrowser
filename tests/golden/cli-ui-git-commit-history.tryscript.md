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
An address with a short commit ID says it needs the full one, and a folder that is not a
repository has no Git panel listening.

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
      "navPanel": "git",
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
      "navPanel": "git",
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
      "navPanel": "git",
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
      "navPanel": "git",
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
    "navPanel": "git",
    "requests": []
  },
  "stepping on while the commit loads": {
    "url": "/view/src/a.py",
    "pane": "file src/a.py",
    "owner": "file",
    "navPanel": "git",
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
      "pane": "Full commit ID needed: A commit’s address uses its full 40- or 64-character ID, not “aaaaaaa”. Open the commit from the Git tab to get it.",
      "owner": "git",
      "navPanel": "git",
      "requests": [
        "GET /api/git/commit/aaaaaaa"
      ]
    },
    "landed": {
      "url": "/commit/aaaaaaa",
      "pane": "Full commit ID needed: A commit’s address uses its full 40- or 64-character ID, not “aaaaaaa”. Open the commit from the Git tab to get it.",
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
  }
}
? 0
```
