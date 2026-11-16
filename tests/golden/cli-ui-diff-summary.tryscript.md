---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Diff’s Summary of Its Changed Files

A diff of more than one file opens with its Diff summary, collapsed: a header that says
what the change set holds, such as “35 changed files (2 added, 3 removed, 30 modified)
+1,234 −3,423”, and opens to its files as a tree by folder.
This browserless session loads the production code that decides it: the shell’s
changed-files tree (`static/changed-files-tree.js`), which the Pulls tab’s tree of a
pull request’s files is drawn on too, for the header’s words, the roll-ups, and the rows
a reader sees; `builtin_plugins/diff/diff-model.js` for what each change of a manifest
is as a row; and `builtin_plugins/diff/diff-summary.js` for the tree’s decisions.

The header lists only the statuses some file has, in one order: added, removed,
modified, renamed, then the rest.
Counts use the shell’s number format, the minus sign is U+2212, and “(estimated)”
follows totals that are not exact.
`numbers` are the counts the header paints bold, the file count and then each status’s,
each apart from its words, which stay regular (`docs/design-system.md`, “Count Summaries
Bold Their Numbers”). A screen reader is told the same in words.
In the tree, every folder carries the line counts of the files under it, open or closed,
and says how many of them have no counts, as a binary file has none.
A chain of single folders is one row.
Counts are written as the rows write them (`changeStats`), and a folder says what its
sums leave out, for each side when the sides differ.
A path a patch lists more than once, as a file that became a symlink or a commit series
repeats it, is one row with both changes’ counts and a status for what happened to it,
so the root’s counts are the header’s totals.
A long tree has in the document only the rows in its box’s view, 40 more each way, and
the row that takes Tab.
A path is its author’s text, so a control, format, or invisible character in it, such as
a right-to-left override or a zero-width space, shows as U+FFFD by the server’s display
rule (`displayPath`), while the path itself stays the row’s identity.
The arrow keys move along the rows, Right and Left open, close, and step into or out of
a folder, and only Enter, Space, or a press on a file jumps the diff to it, since the
tree sits above the files a jump scrolls to.
`invariants` are relations the session holds: the breakdown counts each file once, each
folder’s counts are the sums of its files’, the root’s are the manifest’s totals, every
file row names a path the diff finds it by, and the header’s counted parts read as its
words.

```console
$ node tests/dom/diff-summary-session.js
{
  "stories": {
    "the reader's example": {
      "text": "35 changed files (2 added, 3 removed, 30 modified)  +1,234 −3,423",
      "label": "35 changed files: 2 added, 3 removed, 30 modified; 1,234 lines added, 3,423 deleted",
      "estimated": false,
      "numbers": [
        "35",
        "2",
        "3",
        "30"
      ]
    },
    "every kind, in the header's order": {
      "text": "11 changed files (3 added, 1 removed, 3 modified, 1 renamed, 1 copied, 1 type changed, 1 unmerged)  +669 −60",
      "label": "11 changed files: 3 added, 1 removed, 3 modified, 1 renamed, 1 copied, 1 type changed, 1 unmerged; 669 lines added, 60 deleted",
      "estimated": false,
      "numbers": [
        "11",
        "3",
        "1",
        "3",
        "1",
        "1",
        "1",
        "1"
      ]
    },
    "each change as a row": [
      "modified -> modified README.md",
      "added -> added src/app/new.py",
      "deleted -> removed src/app/old.py",
      "renamed -> renamed src/app/views/main.py (from src/app/main.py)",
      "copied -> copied src/app/views/copy.py (from src/app/views/main.py)",
      "type_changed -> changed tools/run",
      "unmerged -> unmerged src/app/conflict.py",
      "added -> added assets/logo.png",
      "modified -> modified assets/icon.png",
      "modified -> modified src/viewer/plugins/diff/diff-view.js",
      "added -> added src/viewer/plugins/diff/diff-summary.js"
    ],
    "a change set whose totals are not exact": {
      "text": "11 changed files (3 added, 1 removed, 3 modified, 1 renamed, 1 copied, 1 type changed, 1 unmerged)  +? −? (estimated)",
      "label": "11 changed files: 3 added, 1 removed, 3 modified, 1 renamed, 1 copied, 1 type changed, 1 unmerged; line counts unknown, estimated",
      "estimated": true,
      "numbers": [
        "11",
        "3",
        "1",
        "3",
        "1",
        "1",
        "1",
        "1"
      ]
    },
    "one status, one file of it": {
      "text": "2 changed files (2 modified)  +2 −1",
      "label": "2 changed files: 2 modified; 2 lines added, 1 deleted",
      "estimated": false,
      "numbers": [
        "2",
        "2"
      ]
    },
    "no files": {
      "text": "0 changed files  +0 −0",
      "label": "0 changed files; 0 lines added, 0 deleted",
      "estimated": false,
      "numbers": [
        "0"
      ]
    },
    "the tree as it opens": [
      "v assets/ (2; 2 files without line counts)",
      "  M icon.png",
      "  A logo.png",
      "v src/ (7; 1 file without line counts) +666 −59",
      "  v app/ (5; 1 file without line counts) +46 −24",
      "    v views/ (2) +6 −2",
      "      C copy.py (from src/app/views/main.py) +1 −0",
      "      R main.py (from src/app/main.py) +5 −2",
      "    U conflict.py",
      "    A new.py +40 −0",
      "    D old.py +0 −22",
      "  v viewer/plugins/diff/ (2) +620 −35",
      "    A diff-summary.js +400 −0",
      "    M diff-view.js +220 −35",
      "v tools/ (1) +0 −0",
      "  T run +0 −0",
      "M README.md +3 −1"
    ],
    "past the threshold only the top level shows": [
      "> assets/ (2; 2 files without line counts)",
      "> src/ (7; 1 file without line counts) +666 −59",
      "> tools/ (1) +0 −0",
      "M README.md +3 −1"
    ],
    "the keys move along the rows, and only Enter, Space, or a press jumps": [
      {
        "key": "ArrowDown",
        "did": "moved",
        "anchor": "M icon.png"
      },
      {
        "key": "ArrowRight",
        "did": "none",
        "anchor": "M icon.png"
      },
      {
        "key": "ArrowDown",
        "did": "moved",
        "anchor": "A logo.png"
      },
      {
        "key": "ArrowDown",
        "did": "moved",
        "anchor": "v src/ (7; 1 file without line counts) +666 −59"
      },
      {
        "key": "Enter",
        "did": "toggled",
        "anchor": "> src/ (7; 1 file without line counts) +666 −59"
      },
      {
        "key": "ArrowRight",
        "did": "toggled",
        "anchor": "v src/ (7; 1 file without line counts) +666 −59"
      },
      {
        "key": "ArrowRight",
        "did": "moved",
        "anchor": "v app/ (5; 1 file without line counts) +46 −24"
      },
      {
        "key": "ArrowLeft",
        "did": "toggled",
        "anchor": "> app/ (5; 1 file without line counts) +46 −24"
      },
      {
        "key": "ArrowLeft",
        "did": "moved",
        "anchor": "v src/ (7; 1 file without line counts) +666 −59"
      },
      {
        "key": "ArrowLeft",
        "did": "toggled",
        "anchor": "> src/ (7; 1 file without line counts) +666 −59"
      },
      {
        "key": "End",
        "did": "moved",
        "anchor": "M README.md +3 −1"
      },
      {
        "key": " ",
        "did": "jump",
        "path": "README.md",
        "anchor": "M README.md +3 −1"
      },
      {
        "key": "Home",
        "did": "moved",
        "anchor": "v assets/ (2; 2 files without line counts)"
      },
      {
        "key": "ArrowUp",
        "did": "none",
        "anchor": "v assets/ (2; 2 files without line counts)"
      },
      {
        "key": "ArrowRight",
        "did": "moved",
        "anchor": "M icon.png"
      },
      {
        "key": "Escape",
        "did": "not the tree's",
        "anchor": "M icon.png"
      }
    ],
    "after the walk": [
      "v assets/ (2; 2 files without line counts)",
      "  M icon.png",
      "  A logo.png",
      "> src/ (7; 1 file without line counts) +666 −59",
      "v tools/ (1) +0 −0",
      "  T run +0 −0",
      "M README.md +3 −1"
    ],
    "closing a folder keeps the row that takes Tab, on the folder": {
      "did": "toggled",
      "anchor": "src/viewer/plugins/diff/",
      "rows": [
        "v assets/ (2; 2 files without line counts)",
        "  M icon.png",
        "  A logo.png",
        "v src/ (7; 1 file without line counts) +666 −59",
        "  v app/ (5; 1 file without line counts) +46 −24",
        "    v views/ (2) +6 −2",
        "      C copy.py (from src/app/views/main.py) +1 −0",
        "      R main.py (from src/app/main.py) +5 −2",
        "    U conflict.py",
        "    A new.py +40 −0",
        "    D old.py +0 −22",
        "  > viewer/plugins/diff/ (2) +620 −35",
        "v tools/ (1) +0 −0",
        "  T run +0 −0",
        "M README.md +3 −1"
      ],
      "file": {
        "kind": "jump",
        "path": "README.md"
      }
    },
    "a path's control and invisible characters show as U+FFFD": {
      "rows": [
        "v docs/ (2) +2 <U+2212>1",
        "  R new<U+FFFD>name.md (from docs/old<U+FFFD>name.md) +1 <U+2212>0",
        "  M zero<U+FFFD>width.md +1 <U+2212>1",
        "v src/ (1) +3 <U+2212>0",
        "  A evil<U+FFFD>gnp.js +3 <U+2212>0"
      ],
      "identities": [
        "docs/new<U+200B>name.md",
        "docs/zero<U+200B>width.md",
        "src/evil<U+202E>gnp.js"
      ]
    },
    "a path a patch lists twice is one row": {
      "a file that became a symlink": {
        "header": "3 changed files (1 added, 1 removed, 1 modified)  +3 −4",
        "rows": [
          "v bin/ (1) +1 −3",
          "  T run +1 −3",
          "M README.md +2 −1"
        ],
        "rootMatchesTotals": true
      },
      "a format-patch series of two commits": {
        "header": "6 changed files (1 added, 1 removed, 4 modified)  +12 −7",
        "rows": [
          "v src/ (3) +12 −7",
          "  M a.py +5 −1",
          "  A b.py +6 −1",
          "  D c.py +1 −5"
        ],
        "rootMatchesTotals": true
      }
    },
    "a folder says what its sums leave out": [
      {
        "row": "v lib/ (3; 1 file without an added count, 2 files without deleted counts) +6 −2",
        "label": "lib, 3 files, 6 added, 2 deleted, 1 file without an added count, 2 files without deleted counts"
      },
      {
        "row": "  M half.py +4 −?",
        "label": "half.py, modified, 4 added, unknown deleted"
      },
      {
        "row": "  A logo.png",
        "label": "logo.png, added"
      },
      {
        "row": "  M whole.py +2 −2",
        "label": "whole.py, modified, 2 added, 2 deleted"
      }
    ],
    "a long tree draws its view, its overscan, and the row that takes Tab": {
      "at the top": {
        "range": {
          "start": 0,
          "end": 60
        },
        "rows": 60,
        "first": 0,
        "last": 59
      },
      "scrolled to the middle": {
        "range": {
          "start": 460,
          "end": 560
        },
        "rows": 101,
        "first": 0,
        "last": 559
      },
      "the row that takes Tab far below": {
        "range": {
          "start": 0,
          "end": 60
        },
        "rows": 61,
        "first": 0,
        "last": 1101
      }
    }
  },
  "invariants": {
    "the breakdown counts every file once": true,
    "each folder's lines are the sum of its files' known lines": true,
    "the root's lines are the manifest's totals": true,
    "every file row jumps to a path the diff finds it by": true,
    "a closed tree's rows are the top level": true,
    "the header's counted parts read as its words": true
  }
}
? 0
```
