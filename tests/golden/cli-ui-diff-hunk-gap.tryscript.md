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
Opening one asks the comparison’s `view=lines` once for up to `DIFF_GAP_LINES` of them,
nearest the hunk, by their end above a hunk and their start below one, and draws them as
the patch’s own context lines are drawn, both line numbers advancing together; a longer
gap, or one whose answer the route’s byte bound cut short because its lines are long,
leaves a bar of the same kind for the rest, at the far end of the group, as one step
more. The bar says how many lines it holds closed and how many it shows open, its steps’
among them, and closing it closes its steps.
What it read is kept while the diff is mounted, so opening it again, or drawing it in
Split or Current, asks for nothing.
A gap opened above the pane’s top pushes nothing the reader is looking at.
Its lines are highlighted as the hunks’ are, within the file’s syntax bound, which
counts the hunks and every gap highlighted so far.
A bar below a last hunk that turns out to end the file goes, and a reader who pressed it
from the keyboard goes on from the file’s bar.
A last line with no newline says so, as the patch’s own does.
A load that fails closes the bar saying so, and a press asks again.
A file whose lines the comparison declines, or whose answer names another comparison, as
a ref that moved since the diff was drawn gives, even one whose file ends before the
lines asked for, draws its separators as before, under one line that says so, and a
patch file, which names no snapshot, draws plain separators.

This browserless session loads the production `builtin_plugins/diff/diff-view.js` and
`builtin_plugins/diff/diff-fold.js` and mounts a comparison of eight files into an
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
        "HEAD src/app.py lines end=7 count=6"
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
        "HEAD src/app.py lines end=77 count=25"
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
        "HEAD src/app.py lines end=52 count=25"
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
        "HEAD src/app.py lines end=52 count=25"
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
        "HEAD src/app.py lines start=84 count=25"
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
      "step": "A file whose lines the comparison declines draws plain separators, saying so",
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
        "HEAD notes.txt lines end=10 count=9"
      ],
      "console": [
        "metabrowser diff: the comparison declines this file's lines"
      ]
    },
    {
      "step": "An answer its byte bound cuts short opens the lines nearest the hunk, the rest behind a bar",
      "wide.json": [
        "v [Hide 4 lines] @@ -147,7 +147,7 @@",
        "> [142 unchanged lines]",
        "4 rows: 143 143 | row 143 ... 146 146 | row 146",
        "147 147 | row 147",
        "148 148 | row 148",
        "149 149 | row 149",
        "150 - |-row 150",
        "- 150 |+row 150, changed",
        "151 151 | row 151",
        "152 152 | row 152",
        "153 153 | row 153",
        "> [Rest of the file]"
      ],
      "asks": [
        "HEAD wide.json lines end=147 count=25"
      ]
    },
    {
      "step": "Its next step asks once more, up to the lines it drew",
      "wide.json": [
        "v [Hide 8 lines] @@ -147,7 +147,7 @@",
        "v [Hide 4 lines]",
        "> [138 unchanged lines]",
        "8 rows: 139 139 | row 139 ... 146 146 | row 146",
        "147 147 | row 147",
        "148 148 | row 148",
        "149 149 | row 149",
        "150 - |-row 150",
        "- 150 |+row 150, changed",
        "151 151 | row 151",
        "152 152 | row 152",
        "153 153 | row 153",
        "> [Rest of the file]"
      ],
      "asks": [
        "HEAD wide.json lines end=143 count=25"
      ]
    },
    {
      "step": "Closed and opened again, it opens to the lines it read, asking for none",
      "wide.json": [
        "v [Hide 4 lines] @@ -147,7 +147,7 @@",
        "> [142 unchanged lines]",
        "4 rows: 143 143 | row 143 ... 146 146 | row 146",
        "147 147 | row 147",
        "148 148 | row 148",
        "149 149 | row 149",
        "150 - |-row 150",
        "- 150 |+row 150, changed",
        "151 151 | row 151",
        "152 152 | row 152",
        "153 153 | row 153",
        "> [Rest of the file]"
      ],
      "asks": []
    },
    {
      "step": "Below the last hunk too: the lines nearest the hunk, then a bar for the rest",
      "wide.json": [
        "v [Hide 4 lines] @@ -147,7 +147,7 @@",
        "> [142 unchanged lines]",
        "4 rows: 143 143 | row 143 ... 146 146 | row 146",
        "147 147 | row 147",
        "148 148 | row 148",
        "149 149 | row 149",
        "150 - |-row 150",
        "- 150 |+row 150, changed",
        "151 151 | row 151",
        "152 152 | row 152",
        "153 153 | row 153",
        "v [Hide 4 lines]",
        "4 rows: 154 154 | row 154 ... 157 157 | row 157",
        "> [43 unchanged lines]"
      ],
      "asks": [
        "HEAD wide.json lines start=154 count=25"
      ]
    },
    {
      "step": "A bar below a hunk that ends the file goes, and the keyboard goes on from the file's bar",
      "tail.py": [
        "> [3 unchanged lines] @@ -4,7 +4,7 @@",
        "4 4 | tail 4 *",
        "5 5 | tail 5 *",
        "6 6 | tail 6 *",
        "7 - |-tail 7 *",
        "- 7 |+tail 7, changed *",
        "8 8 | tail 8 *",
        "9 9 | tail 9 *",
        "10 10 | tail 10 *"
      ],
      "asks": [
        "HEAD tail.py lines start=11 count=25"
      ],
      "focused": "diff-file-toggle expanded"
    },
    {
      "step": "A file's last line with no newline says so, as the patch's own does",
      "end.txt": [
        "> [1 unchanged line] @@ -2,7 +2,7 @@",
        "2 2 | end 2",
        "3 3 | end 3",
        "4 4 | end 4",
        "5 - |-end 5",
        "- 5 |+end 5, changed",
        "6 6 | end 6",
        "7 7 | end 7",
        "8 8 | end 8",
        "v [Hide 12 lines]",
        "12 rows: 9 9 | end 9 ... 20 20 | end 20 (no newline)"
      ],
      "asks": [
        "HEAD end.txt lines start=9 count=25"
      ]
    },
    {
      "step": "An answer for another comparison, as a moved ref gives, is declined, saying so, even one that holds no lines",
      "moved.py": [
        "says: The unchanged lines of this file cannot be shown.",
        "= @@ -12,7 +12,7 @@",
        "12 12 | moved 12 *",
        "13 13 | moved 13 *",
        "14 14 | moved 14 *",
        "15 - |-moved 15 *",
        "- 15 |+moved 15, changed *",
        "16 16 | moved 16 *",
        "17 17 | moved 17 *",
        "18 18 | moved 18 *"
      ],
      "shrunk.py": [
        "says: The unchanged lines of this file cannot be shown.",
        "= @@ -42,7 +42,7 @@",
        "42 42 | shrunk 42 *",
        "43 43 | shrunk 43 *",
        "44 44 | shrunk 44 *",
        "45 - |-shrunk 45 *",
        "- 45 |+shrunk 45, changed *",
        "46 46 | shrunk 46 *",
        "47 47 | shrunk 47 *",
        "48 48 | shrunk 48 *"
      ],
      "asks": [
        "HEAD moved.py lines end=12 count=11",
        "HEAD shrunk.py lines end=42 count=25"
      ],
      "console": [
        "metabrowser diff: the comparison declines this file's lines",
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
