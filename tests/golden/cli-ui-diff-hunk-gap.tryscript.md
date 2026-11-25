---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Unchanged Lines Between a Diff’s Hunks

A code file’s diff shows each change with the few lines of context Git writes around it,
and each hunk’s `@@` separator stands for the lines its hunks leave out.
Where the diff came from a comparison, which can read the file’s snapshot, each
separator is the bar every fold of the diff draws (docs/design-system.md, “Fold
Expanders”), with the separator kept beside its label: above each hunk, for the
unchanged lines between it and the hunk above or the file’s start, and below the last
hunk, for the rest of the file, whose end the diff does not know until it asks.
Opening one asks the comparison’s `view=lines` for up to `DIFF_GAP_LINES` of them,
nearest the hunk, and draws them as the patch’s own context lines are drawn, both line
numbers advancing together; a longer gap leaves a bar of the same kind for the rest, at
the far end of the group, as one step more.
The bar says how many lines it holds closed and how many it shows open, its steps’ among
them, and closing it closes its steps.
What it read is kept while the diff is mounted, so opening it again, or drawing it in
Split or Current, asks for nothing.
A gap opened above the pane’s top pushes nothing the reader is looking at.
Its lines are highlighted as the hunks’ are, within the file’s syntax bound, which
counts the hunks and every gap highlighted so far.
A load that fails closes the bar saying so, and a press asks again.
A file whose lines the comparison declines draws its separators as before, under one
line that says so, and a patch file, which names no snapshot, draws plain separators.

This browserless session loads the production `builtin_plugins/diff/diff-view.js` and
`builtin_plugins/diff/diff-fold.js` and mounts a comparison of three files into an
element tree with a model of the pane’s geometry; its gap loader stands in for the
route, whose answers `tests/golden/cli-api-diff-lines.tryscript.md` pins.
`DIFF_GAP_LINES` is 25 here.
A bar prints as `>` closed or `v` open, with what it says and the separator beside it; a
plain separator as `=`; a row as its line numbers, its marker, and its text, `*` where
it is highlighted; and a gap’s run of rows as one line, its count and its first and last
rows.

## Test: Gaps open between, before, and after the hunks

```console
$ node tests/dom/diff-hunk-gap-session.js
{
  "steps": [
    {
      "step": "A comparison: each hunk's separator is a fold's bar, and one more below the last",
      "src/app.py": [
        "> [6 unchanged lines] @@ -7,6 +7,7 @@",
        "7 7 | line 7 *",
        "8 8 | line 8 *",
        "9 9 | line 9 *",
        "- 10 |+added line *",
        "10 11 | line 11 *",
        "11 12 | line 12 *",
        "12 13 | line 13 *",
        "> [63 unchanged lines] @@ -76,7 +77,7 @@ def main():",
        "76 77 | line 77 *",
        "77 78 | line 78 *",
        "78 79 | line 79 *",
        "79 - |-line 80 *",
        "- 80 |+line 80, changed *",
        "80 81 | line 81 *",
        "81 82 | line 82 *",
        "82 83 | line 83 *",
        "> [Rest of the file]"
      ],
      "notes.txt": [
        "> [9 unchanged lines] @@ -10,7 +10,7 @@",
        "10 10 | note 10",
        "11 11 | note 11",
        "12 12 | note 12",
        "13 - |-note 13 before",
        "- 13 |+note 13",
        "14 14 | note 14",
        "15 15 | note 15",
        "16 16 | note 16",
        "> [Rest of the file]"
      ],
      "logo.png": [
        "says: Binary file; no textual diff."
      ],
      "asks": []
    },
    {
      "step": "The bar above the first hunk opens to the file's first lines",
      "src/app.py": [
        "v [Hide 6 lines] @@ -7,6 +7,7 @@",
        "6 rows: 1 1 | line 1 * ... 6 6 | line 6 *",
        "7 7 | line 7 *",
        "8 8 | line 8 *",
        "9 9 | line 9 *",
        "- 10 |+added line *",
        "10 11 | line 11 *",
        "11 12 | line 12 *",
        "12 13 | line 13 *",
        "> [63 unchanged lines] @@ -76,7 +77,7 @@ def main():",
        "76 77 | line 77 *",
        "77 78 | line 78 *",
        "78 79 | line 79 *",
        "79 - |-line 80 *",
        "- 80 |+line 80, changed *",
        "80 81 | line 81 *",
        "81 82 | line 82 *",
        "82 83 | line 83 *",
        "> [Rest of the file]"
      ],
      "asks": [
        "HEAD src/app.py lines 1+6"
      ],
      "highlighted": [
        "python: 6 lines"
      ]
    },
    {
      "step": "The gap between the hunks opens its 25 lines nearest the hunk below",
      "src/app.py": [
        "v [Hide 6 lines] @@ -7,6 +7,7 @@",
        "6 rows: 1 1 | line 1 * ... 6 6 | line 6 *",
        "7 7 | line 7 *",
        "8 8 | line 8 *",
        "9 9 | line 9 *",
        "- 10 |+added line *",
        "10 11 | line 11 *",
        "11 12 | line 12 *",
        "12 13 | line 13 *",
        "v [Hide 25 lines] @@ -76,7 +77,7 @@ def main():",
        "> [38 unchanged lines]",
        "25 rows: 51 52 | line 52 * ... 75 76 | line 76 *",
        "76 77 | line 77 *",
        "77 78 | line 78 *",
        "78 79 | line 79 *",
        "79 - |-line 80 *",
        "- 80 |+line 80, changed *",
        "80 81 | line 81 *",
        "81 82 | line 82 *",
        "82 83 | line 83 *",
        "> [Rest of the file]"
      ],
      "asks": [
        "HEAD src/app.py lines 52+25"
      ],
      "rowAtTopBefore": "76 77 | line 77 * at 0 px",
      "rowAtTopAfter": "76 77 | line 77 * at 0 px",
      "highlighted": [
        "python: 25 lines"
      ]
    },
    {
      "step": "Its next step's lines do not load: the bar closes and says so",
      "src/app.py": [
        "v [Hide 6 lines] @@ -7,6 +7,7 @@",
        "6 rows: 1 1 | line 1 * ... 6 6 | line 6 *",
        "7 7 | line 7 *",
        "8 8 | line 8 *",
        "9 9 | line 9 *",
        "- 10 |+added line *",
        "10 11 | line 11 *",
        "11 12 | line 12 *",
        "12 13 | line 13 *",
        "v [Hide 25 lines] @@ -76,7 +77,7 @@ def main():",
        "> [Could not load 38 unchanged lines. Retry]",
        "25 rows: 51 52 | line 52 * ... 75 76 | line 76 *",
        "76 77 | line 77 *",
        "77 78 | line 78 *",
        "78 79 | line 79 *",
        "79 - |-line 80 *",
        "- 80 |+line 80, changed *",
        "80 81 | line 81 *",
        "81 82 | line 82 *",
        "82 83 | line 83 *",
        "> [Rest of the file]"
      ],
      "asks": [
        "HEAD src/app.py lines 27+25"
      ],
      "console": [
        "metabrowser diff: a gap's lines did not load"
      ]
    },
    {
      "step": "A press asks again, and the next 25 lines are drawn above the last",
      "src/app.py": [
        "v [Hide 6 lines] @@ -7,6 +7,7 @@",
        "6 rows: 1 1 | line 1 * ... 6 6 | line 6 *",
        "7 7 | line 7 *",
        "8 8 | line 8 *",
        "9 9 | line 9 *",
        "- 10 |+added line *",
        "10 11 | line 11 *",
        "11 12 | line 12 *",
        "12 13 | line 13 *",
        "v [Hide 50 lines] @@ -76,7 +77,7 @@ def main():",
        "v [Hide 25 lines]",
        "> [13 unchanged lines]",
        "50 rows: 26 27 | line 27 * ... 75 76 | line 76 *",
        "76 77 | line 77 *",
        "77 78 | line 78 *",
        "78 79 | line 79 *",
        "79 - |-line 80 *",
        "- 80 |+line 80, changed *",
        "80 81 | line 81 *",
        "81 82 | line 82 *",
        "82 83 | line 83 *",
        "> [Rest of the file]"
      ],
      "asks": [
        "HEAD src/app.py lines 27+25"
      ],
      "highlighted": [
        "python: 25 lines"
      ]
    },
    {
      "step": "Below the last hunk: the rest of the file, whose end the answer says",
      "src/app.py": [
        "v [Hide 6 lines] @@ -7,6 +7,7 @@",
        "6 rows: 1 1 | line 1 * ... 6 6 | line 6 *",
        "7 7 | line 7 *",
        "8 8 | line 8 *",
        "9 9 | line 9 *",
        "- 10 |+added line *",
        "10 11 | line 11 *",
        "11 12 | line 12 *",
        "12 13 | line 13 *",
        "v [Hide 50 lines] @@ -76,7 +77,7 @@ def main():",
        "v [Hide 25 lines]",
        "> [13 unchanged lines]",
        "50 rows: 26 27 | line 27 * ... 75 76 | line 76 *",
        "76 77 | line 77 *",
        "77 78 | line 78 *",
        "78 79 | line 79 *",
        "79 - |-line 80 *",
        "- 80 |+line 80, changed *",
        "80 81 | line 81 *",
        "81 82 | line 82 *",
        "82 83 | line 83 *",
        "v [Hide 25 lines]",
        "25 rows: 83 84 | line 84 ... 107 108 | line 108",
        "> [12 unchanged lines]"
      ],
      "asks": [
        "HEAD src/app.py lines 84+25"
      ],
      "highlighted": []
    },
    {
      "step": "Closing a gap closes its steps too",
      "src/app.py": [
        "v [Hide 6 lines] @@ -7,6 +7,7 @@",
        "6 rows: 1 1 | line 1 * ... 6 6 | line 6 *",
        "7 7 | line 7 *",
        "8 8 | line 8 *",
        "9 9 | line 9 *",
        "- 10 |+added line *",
        "10 11 | line 11 *",
        "11 12 | line 12 *",
        "12 13 | line 13 *",
        "> [63 unchanged lines] @@ -76,7 +77,7 @@ def main():",
        "76 77 | line 77 *",
        "77 78 | line 78 *",
        "78 79 | line 79 *",
        "79 - |-line 80 *",
        "- 80 |+line 80, changed *",
        "80 81 | line 81 *",
        "81 82 | line 82 *",
        "82 83 | line 83 *",
        "v [Hide 25 lines]",
        "25 rows: 83 84 | line 84 ... 107 108 | line 108",
        "> [12 unchanged lines]"
      ],
      "asks": []
    },
    {
      "step": "Opened again, it shows its first lines from what it read, asking for none",
      "src/app.py": [
        "v [Hide 6 lines] @@ -7,6 +7,7 @@",
        "6 rows: 1 1 | line 1 * ... 6 6 | line 6 *",
        "7 7 | line 7 *",
        "8 8 | line 8 *",
        "9 9 | line 9 *",
        "- 10 |+added line *",
        "10 11 | line 11 *",
        "11 12 | line 12 *",
        "12 13 | line 13 *",
        "v [Hide 25 lines] @@ -76,7 +77,7 @@ def main():",
        "> [38 unchanged lines]",
        "25 rows: 51 52 | line 52 * ... 75 76 | line 76 *",
        "76 77 | line 77 *",
        "77 78 | line 78 *",
        "78 79 | line 79 *",
        "79 - |-line 80 *",
        "- 80 |+line 80, changed *",
        "80 81 | line 81 *",
        "81 82 | line 82 *",
        "82 83 | line 83 *",
        "v [Hide 25 lines]",
        "25 rows: 83 84 | line 84 ... 107 108 | line 108",
        "> [12 unchanged lines]"
      ],
      "asks": []
    },
    {
      "step": "Split draws the open gaps' lines on both sides, at both numbers",
      "src/app.py": [
        "v [Hide 6 lines] @@ -7,6 +7,7 @@",
        "6 rows: 1 line 1 || 1 line 1 ... 6 line 6 || 6 line 6",
        "7 line 7 || 7 line 7",
        "8 line 8 || 8 line 8",
        "9 line 9 || 9 line 9",
        "-  || 10 added line",
        "10 line 11 || 11 line 11",
        "11 line 12 || 12 line 12",
        "12 line 13 || 13 line 13",
        "v [Hide 25 lines] @@ -76,7 +77,7 @@ def main():",
        "> [38 unchanged lines]",
        "25 rows: 51 line 52 || 52 line 52 ... 75 line 76 || 76 line 76",
        "76 line 77 || 77 line 77",
        "77 line 78 || 78 line 78",
        "78 line 79 || 79 line 79",
        "79 line 80 || 80 line 80, changed",
        "80 line 81 || 81 line 81",
        "81 line 82 || 82 line 82",
        "82 line 83 || 83 line 83",
        "v [Hide 25 lines]",
        "25 rows: 83 line 84 || 84 line 84 ... 107 line 108 || 108 line 108",
        "> [12 unchanged lines]"
      ],
      "asks": []
    },
    {
      "step": "Current draws them at their new numbers",
      "src/app.py": [
        "v [Hide 6 lines] @@ +7,7 @@",
        "6 rows: 1 | line 1 * ... 6 | line 6 *",
        "7 | line 7 *",
        "8 | line 8 *",
        "9 | line 9 *",
        "10 |+added line *",
        "11 | line 11 *",
        "12 | line 12 *",
        "13 | line 13 *",
        "v [Hide 25 lines] @@ +77,7 @@",
        "> [38 unchanged lines]",
        "25 rows: 52 | line 52 * ... 76 | line 76 *",
        "77 | line 77 *",
        "78 | line 78 *",
        "79 | line 79 *",
        "80 |+line 80, changed *",
        "81 | line 81 *",
        "82 | line 82 *",
        "83 | line 83 *",
        "v [Hide 25 lines]",
        "25 rows: 84 | line 84 ... 108 | line 108",
        "> [12 unchanged lines]"
      ],
      "asks": []
    },
    {
      "step": "A file whose lines the comparison declines draws plain separators, saying why",
      "notes.txt": [
        "says: The unchanged lines of this file cannot be shown.",
        "= @@ -10,7 +10,7 @@",
        "10 10 | note 10",
        "11 11 | note 11",
        "12 12 | note 12",
        "13 - |-note 13 before",
        "- 13 |+note 13",
        "14 14 | note 14",
        "15 15 | note 15",
        "16 16 | note 16"
      ],
      "asks": [
        "HEAD notes.txt lines 1+9"
      ],
      "console": [
        "metabrowser diff: the comparison declines this file's lines"
      ]
    },
    {
      "step": "A patch file names no snapshot, so its separators do not open",
      "src/app.py": [
        "= @@ -7,6 +7,7 @@",
        "7 7 | line 7 *",
        "8 8 | line 8 *",
        "9 9 | line 9 *",
        "- 10 |+added line *",
        "10 11 | line 11 *",
        "11 12 | line 12 *",
        "12 13 | line 13 *",
        "= @@ -76,7 +77,7 @@ def main():",
        "76 77 | line 77 *",
        "77 78 | line 78 *",
        "78 79 | line 79 *",
        "79 - |-line 80 *",
        "- 80 |+line 80, changed *",
        "80 81 | line 81 *",
        "81 82 | line 82 *",
        "82 83 | line 83 *"
      ],
      "asks": []
    }
  ]
}
? 0
```
