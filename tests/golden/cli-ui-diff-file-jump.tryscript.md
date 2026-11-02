---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Going to a File of a Large Diff

A large comparison’s files past its first page are bars until a reader reaches them.
`scrollToFile(path)` is the diff view’s way to one, for a list of the comparison’s
files: it takes a path, because a list from GitHub knows a path and not a file id, and
it answers at once with what it did.
It puts the file at the top of the pane, asks for that file’s lines first, cancels
whatever else was being asked for, and keeps the file there as anything else fills in.
[Rendering Large Content](../../docs/large-content-rendering.md#going-to-a-file) holds
the contract and `tests/dom/diff-file-jump-session.js` says how this session lays itself
out.

It also shows ordinary hydration: the file on screen nearest the top is asked for, one
at a time, the file at the top of the pane stays where it is as others fill in, and a
diff with files still to load says how many.

The session asserts, and so prints nothing for, that no step of a held key has two
requests in flight or a bar off the top, that a neighbour filling in does not move a
jump’s file, that a wheel hands the place back to the reader, and that disposing cancels
the request, lets go of its listeners, and answers `disposed`.

```console
$ node tests/dom/diff-file-jump-session.js
{
  "steps": [
    {
      "step": "mounted: the first file's lines, no request past what is on screen",
      "atTop": "first.py",
      "asked": [
        "src/a.py (waiting)"
      ],
      "partial": "2 of 10 files loaded; the rest load as you reach them"
    },
    {
      "step": "fileForPath: a rename's new path, its old path, a deleted file's, and one it lacks",
      "answers": [
        {
          "fileId": "f4",
          "kind": "renamed",
          "availability": "deferred"
        },
        {
          "fileId": "f4",
          "kind": "renamed",
          "availability": "deferred"
        },
        {
          "fileId": "f5",
          "kind": "deleted",
          "availability": "deferred"
        },
        null
      ]
    },
    {
      "step": "a path this comparison does not hold is an answer, and nothing moves",
      "answer": {
        "kind": "not_in_comparison",
        "path": "only/on/github.py",
        "listTruncated": false
      },
      "atTop": "first.py",
      "asked": [
        "src/a.py (waiting)"
      ],
      "partial": "2 of 10 files loaded; the rest load as you reach them",
      "moved": false
    },
    {
      "step": "the same in a list that stopped at its bound says so",
      "answer": {
        "kind": "not_in_comparison",
        "path": "past/the/cap.py",
        "listTruncated": true
      },
      "atTop": "first.py",
      "asked": [],
      "partial": "2 of 10 files loaded; the rest load as you reach them"
    },
    {
      "step": "a jump after a quiet moment: at the top at once, and asked for at once",
      "answer": {
        "kind": "jumped",
        "fileId": "f8",
        "path": "src/h.py",
        "availability": "deferred"
      },
      "atTop": "src/h.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/h.py (waiting)"
      ],
      "partial": "2 of 10 files loaded; the rest load as you reach them",
      "targetTop": 0
    },
    {
      "step": "its lines are in the page, in a frame of their own",
      "atTop": "src/h.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/h.py"
      ],
      "partial": "3 of 10 files loaded; the rest load as you reach them",
      "lines": "painted",
      "targetTop": 0,
      "lineRows": 3
    },
    {
      "step": "neighbours on screen follow, one at a time, once the jump has what it asked for",
      "atTop": "src/h.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/h.py",
        "src/i.py (waiting)"
      ],
      "partial": "3 of 10 files loaded; the rest load as you reach them",
      "targetTop": 0
    },
    {
      "step": "everything on screen has arrived, and the file has not moved",
      "atTop": "src/h.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/h.py",
        "src/i.py",
        "src/last.py (cancelled)"
      ],
      "partial": "4 of 10 files loaded; the rest load as you reach them",
      "targetTop": 0
    },
    {
      "step": "the last file reaches the top: room past the end, which is what it takes",
      "answer": {
        "kind": "jumped",
        "fileId": "f10",
        "path": "src/last.py",
        "availability": "deferred"
      },
      "atTop": "src/last.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/last.py (waiting)"
      ],
      "partial": "2 of 10 files loaded; the rest load as you reach them",
      "targetTop": 0,
      "roomPastTheEnd": "190px"
    },
    {
      "step": "with its lines there is less room to add, and it is still at the top",
      "atTop": "src/last.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/last.py"
      ],
      "partial": "3 of 10 files loaded; the rest load as you reach them",
      "targetTop": 0,
      "roomPastTheEnd": "330px"
    },
    {
      "step": "a key held through seven files: at most the first request and none since",
      "atTop": "src/i.py",
      "asked": [
        "src/a.py (cancelled)"
      ],
      "partial": "2 of 10 files loaded; the rest load as you reach them",
      "outcomes": [
        "superseded",
        "superseded",
        "superseded",
        "superseded",
        "superseded",
        "superseded"
      ]
    },
    {
      "step": "the key comes up: after the quiet moment, the file it rests on",
      "atTop": "src/i.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/i.py (waiting)"
      ],
      "partial": "2 of 10 files loaded; the rest load as you reach them"
    },
    {
      "step": "a file the server refuses: an answer, and it says so where the lines would be",
      "atTop": "src/f.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/f.py"
      ],
      "partial": "3 of 10 files loaded; the rest load as you reach them",
      "lines": "failed",
      "body": "Could not load this file's changes."
    },
    {
      "step": "a binary file has no lines to ask for",
      "answer": {
        "kind": "jumped",
        "fileId": "f2",
        "path": "gone.bin",
        "availability": "binary"
      },
      "atTop": "gone.bin",
      "asked": [
        "src/a.py (cancelled)",
        "src/f.py"
      ],
      "partial": "3 of 10 files loaded; the rest load as you reach them",
      "lines": "none"
    },
    {
      "step": "a file already here",
      "answer": {
        "kind": "jumped",
        "fileId": "f1",
        "path": "first.py",
        "availability": "ready"
      },
      "atTop": "first.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/f.py"
      ],
      "partial": "3 of 10 files loaded; the rest load as you reach them",
      "lines": "painted"
    },
    {
      "step": "the reader scrolls: the topmost file on screen is asked for, not all of them",
      "atTop": "src/f.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/moved.py (cancelled)",
        "src/f.py (waiting)"
      ],
      "partial": "2 of 10 files loaded; the rest load as you reach them"
    },
    {
      "step": "as they fill in, the file at the top stays",
      "atTop": "src/f.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/moved.py (cancelled)",
        "src/f.py",
        "src/g.py (cancelled)"
      ],
      "partial": "3 of 10 files loaded; the rest load as you reach them",
      "top": 0
    }
  ],
  "reservations": [
    "+10 -0 in unified: 11 rows",
    "+10 -5 in unified: 22 rows",
    "+10 -5 in split: 17 rows",
    "+5000 -0 in unified: 22 rows"
  ],
  "placements": [
    {
      "scrollTop": 400,
      "spacer": 0
    },
    {
      "scrollTop": 400,
      "spacer": 200
    },
    {
      "scrollTop": 0,
      "spacer": 370
    }
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
