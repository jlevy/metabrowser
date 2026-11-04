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

And it shows a first page of ready files, which the mount does not draw whole: rows for
the files within the pane and one screen more, and every later ready file held as a bar
that reserves its own rows, drawn one a frame from the answer in hand when it is reached
or gone to, never asked for, and counted as loaded.
A diff that fits is drawn whole at mount, as before, and so is one with nothing laid out
to measure.

The session asserts, and so prints nothing for, that no step of a held key has two
requests in flight or a bar off the top, that a neighbour filling in does not move a
jump’s file, that a wheel hands the place back to the reader, and that disposing cancels
the request, lets go of its listeners, and answers `disposed`. For held files it asserts
that none is drawn before it is reached, two are never drawn in one frame, the file at
the top does not move as they fill in, a held key draws nothing it passed, and a view
replaced while one waits for its frame draws nothing more and stops observing.

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
          "kind": "file",
          "path": "src/moved.py",
          "fileId": "f4",
          "changeKind": "renamed",
          "availability": "deferred"
        },
        {
          "kind": "file",
          "path": "src/was.py",
          "fileId": "f4",
          "changeKind": "renamed",
          "availability": "deferred"
        },
        {
          "kind": "file",
          "path": "src/gone.py",
          "fileId": "f5",
          "changeKind": "deleted",
          "availability": "deferred"
        },
        {
          "kind": "not_in_comparison",
          "path": "only/on/github.py",
          "listTruncated": false
        }
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
      "partial": "2 of 10 files loaded; 1 could not be loaded; the rest load as you reach them",
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
      "partial": "2 of 10 files loaded; 1 could not be loaded; the rest load as you reach them",
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
      "partial": "2 of 10 files loaded; 1 could not be loaded; the rest load as you reach them",
      "lines": "painted"
    },
    {
      "step": "an abandoned request's late rejection is not its file's answer",
      "scheduler": [
        "render f7"
      ]
    },
    {
      "step": "a render that throws after its file is settled: said, counted, the frame clean",
      "atTop": "src/h.py",
      "asked": [
        "src/a.py (cancelled)",
        "src/h.py"
      ],
      "partial": "2 of 10 files loaded; 1 could not be loaded; the rest load as you reach them",
      "lines": "failed",
      "body": "Could not load this file's changes."
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
    },
    {
      "step": "a first file that is too large does not strand the next visible file",
      "atTop": "first.py",
      "asked": [
        "src/a.py",
        "src/moved.py (waiting)"
      ],
      "partial": "3 of 10 files loaded; the rest load as you reach them"
    },
    {
      "step": "a first page of ready files: rows for the first screen and one more, the rest held",
      "atTop": "r1.py",
      "asked": [],
      "partial": "12 of 14 files loaded; the rest load as you reach them",
      "drawn": [
        "r1.py",
        "r2.py",
        "r3.py",
        "r4.py"
      ],
      "reserving": [
        "r5.py",
        "r6.py",
        "r7.py",
        "r8.py",
        "r9.py",
        "r10.py",
        "r11.py",
        "r12.py",
        "d1.py",
        "d2.py"
      ],
      "heldReserves": "calc(8 * var(--diff-code-row-height) + 1 * var(--diff-header-row-height) + 0 * var(--diff-fold-row-height) + 0 * var(--diff-notice-row-height))"
    },
    {
      "step": "fileForPath: a held file is a ready file of the comparison",
      "answers": [
        {
          "kind": "file",
          "path": "r9.py",
          "fileId": "r9",
          "changeKind": "modified",
          "availability": "ready"
        }
      ]
    },
    {
      "step": "the reader scrolls to them: one a frame, topmost first, nothing asked for",
      "atTop": "r6.py",
      "asked": [],
      "partial": "12 of 14 files loaded; the rest load as you reach them",
      "drawnPerFrame": [
        [
          "r6.py"
        ],
        [
          "r7.py"
        ],
        [
          "r8.py"
        ],
        []
      ],
      "top": 0,
      "rows": 8
    },
    {
      "step": "a jump to a held file: at the top at once, its bar's frame first, then its lines",
      "answer": {
        "kind": "jumped",
        "fileId": "r11",
        "path": "r11.py",
        "availability": "ready"
      },
      "atTop": "r11.py",
      "asked": [],
      "partial": "12 of 14 files loaded; the rest load as you reach them",
      "targetTop": 0,
      "rowsInTheBarsFrame": 0,
      "lines": "painted",
      "lineRows": 8
    },
    {
      "step": "held and deferred reservations collapse and return on reopen",
      "atTop": "r1.py",
      "asked": [],
      "partial": "12 of 14 files loaded; the rest load as you reach them",
      "heights": [
        {
          "file": "r5.py",
          "expanded": 180,
          "collapsed": 0,
          "reopened": 180
        },
        {
          "file": "d1.py",
          "expanded": 180,
          "collapsed": 0,
          "reopened": 180
        }
      ]
    },
    {
      "step": "a layout choice updates held and deferred reservations before their rows are drawn",
      "atTop": "r1.py",
      "asked": [],
      "partial": "12 of 14 files loaded; the rest load as you reach them",
      "split": [
        180,
        180
      ],
      "unified": [
        260,
        200
      ]
    },
    {
      "step": "a width-triggered layout change updates held and deferred reservations too",
      "atTop": "r1.py",
      "asked": [],
      "partial": "12 of 14 files loaded; the rest load as you reach them",
      "split": [
        180,
        180
      ]
    },
    {
      "step": "the current-file subscription follows held and deferred bars, suppresses repeats, and stops",
      "files": [
        "r1.py",
        "r9.py",
        "d1.py"
      ]
    },
    {
      "step": "the current-file lookup bisects 2,048 sections",
      "geometryReads": 13
    },
    {
      "step": "a key held over held files: nothing drawn it passed, then the file it rests on",
      "atTop": "r9.py",
      "asked": [],
      "partial": null,
      "outcomes": [
        "superseded",
        "superseded",
        "superseded",
        "superseded",
        "painted"
      ],
      "drawn": [
        "r1.py",
        "r2.py",
        "r3.py",
        "r4.py",
        "r9.py"
      ]
    },
    {
      "step": "held files are loaded: the count is of the files still to come",
      "atTop": "r1.py",
      "asked": [],
      "partial": "6 of 9 files loaded; the rest load as you reach them",
      "drawn": [
        "r1.py",
        "r2.py",
        "r3.py",
        "r4.py"
      ]
    },
    {
      "step": "a diff that fits is drawn whole at mount, as before",
      "atTop": "r1.py",
      "asked": [],
      "partial": null,
      "drawn": [
        "r1.py",
        "r2.py",
        "r3.py"
      ],
      "reserving": 0,
      "observers": 0
    },
    {
      "step": "nothing laid out to measure: every ready file is drawn at mount, as before",
      "atTop": null,
      "asked": [],
      "partial": null,
      "drawn": 12
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
  ],
  "heldRows": [
    "8 added lines in split: 9 rows",
    "context, 3 removed and 5 added, context in unified: 11 rows",
    "context, 3 removed and 5 added, context in split: 8 rows",
    "a run of 50 added lines, which folds in unified: 22 rows",
    "two hunks of one line each, truncated in unified: 5 rows"
  ],
  "firstScreens": [
    "a 400 px pane, the diff 0 px down: 800 px",
    "a 900 px pane, the diff 300 px down: 1500 px",
    "a 900 px pane, the diff 1200 px down: 900 px",
    "nothing measured: Infinity px"
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
