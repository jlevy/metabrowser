---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: line anchors in source views

This session loads the production navigation controller, plugin SDK, source append, and
line-anchor scripts from a command line and renders a source view through
`renderSourceView`. It pins the `#L` grammar the GitHub reducer also accepts, how lines
are counted, what an anchor highlights or says against a partly or fully loaded file,
and what a click or shift-click on a line number sets.
The reader’s session opens a partly loaded file at a line past the loaded part, loads
more, clicks and shift-clicks line numbers, edits the fragment, anchors columns and a
line past the end, and clears the fragment.
Clicks replace the address and never scroll; an edited fragment, or an anchor that Load
more has just reached by appending or by rendering the view again, scrolls its first
line into view once.
The fake layout rounds each line’s height away from the computed `1lh`, as a browser
does, so the line pitch the highlight is placed by must be the one measured from the
gutter, and a zoom change measures it again.
Text with CR and CRLF line endings numbers the lines the browser shows.

It also pins the keyboard and the rest of the reader’s path.
The gutter is a vertical slider that Tab reaches: arrow keys, Page Up, Page Down, Home,
and End move the anchor, Shift extends it from the range’s moving end, and each key
replaces the address and brings the moved line into view.
Paging measures the pane that scrolls the view, not the window.
Its spoken value names the highlighted lines, and a status line says them when the
anchor changes while the gutter does not have focus; a new view’s status line takes its
first words a task after it mounts, so a screen reader announces them.
An address with a line anchor or `plain=1` asks for the Source view, a view rendered
into the shell’s inert stage waits for the fragment event while a Source tab shown for
the first time scrolls to the anchor at once, and a Markdown file’s Source tab shows its
front matter and body as YAML and Markdown blocks under one gutter, whose copy payload
is the file’s text. When only part of that file is loaded, it is one block, so Load more
appends the rest to it rather than to the front matter.

```console
$ node tests/dom/source-line-anchors-session.js
{
  "grammar": {
    "L10": {
      "start": 10,
      "end": 10
    },
    "L10-L20": {
      "start": 10,
      "end": 20
    },
    "L20-L10": {
      "start": 10,
      "end": 20
    },
    "L10C5-L20C8": {
      "start": 10,
      "end": 20
    },
    "L0": null,
    "L1-": null,
    "heading": null,
    "L1234567890": null
  },
  "lineCounts": {
    "empty": 0,
    "one line, no newline": 1,
    "one line, newline": 1,
    "blank last line": 2,
    "partial last line": 2
  },
  "describe": {
    "L12 in the loaded part": {
      "status": "shown",
      "start": 12,
      "end": 12,
      "message": ""
    },
    "L30-L60 across the loaded edge": {
      "status": "partial",
      "start": 30,
      "end": 40,
      "message": "Lines 30–60 continue past the part of this file loaded so far (lines 1–40). Load more to see the rest."
    },
    "L60 not loaded yet": {
      "status": "not-loaded",
      "start": 60,
      "end": 60,
      "message": "Line 60 is past the part of this file loaded so far (lines 1–40). Load more to reach it."
    },
    "L50-L55 not loaded yet": {
      "status": "not-loaded",
      "start": 50,
      "end": 55,
      "message": "Lines 50–55 are past the part of this file loaded so far (lines 1–40). Load more to reach them."
    },
    "L30-L60 past the end": {
      "status": "partial",
      "start": 30,
      "end": 40,
      "message": "Lines 30–60 run past the end of this file, which ends at line 40."
    },
    "L60 past the end": {
      "status": "past-end",
      "start": 60,
      "end": 60,
      "message": "Line 60 is past the end of this file, which has 40 lines."
    },
    "a heading fragment": {
      "status": "none",
      "start": 0,
      "end": 0,
      "message": ""
    }
  },
  "clicks": {
    "click 12": "L12",
    "shift-click 5 from L12": "L5-L12",
    "shift-click 20 from L5-L12": "L5-L20",
    "shift-click 5 from L5": "L5",
    "shift-click 7 without an anchor": "L7",
    "click 7 over L5-L20": "L7"
  },
  "keys": {
    "Down with nothing anchored": {
      "fragment": "L1",
      "focus": 1
    },
    "Down with nothing anchored, line 30 first in view": {
      "fragment": "L30",
      "focus": 30
    },
    "Down from L10-L20": {
      "fragment": "L21",
      "focus": 21
    },
    "Up from L10-L20 moving its first line": {
      "fragment": "L9",
      "focus": 9
    },
    "Shift+Down from L10": {
      "fragment": "L10-L11",
      "focus": 11
    },
    "Shift+Up from L10-L11 moving its last line": {
      "fragment": "L10",
      "focus": 10
    },
    "Shift+Up from L10 across its fixed end": {
      "fragment": "L9-L10",
      "focus": 9
    },
    "Shift+Page Down from L90": {
      "fragment": "L90-L100",
      "focus": 100
    },
    "Page Up from L5": {
      "fragment": "L1",
      "focus": 1
    },
    "Home from L50": {
      "fragment": "L1",
      "focus": 1
    },
    "Shift+End from L50": {
      "fragment": "L50-L100",
      "focus": 100
    },
    "a letter": null,
    "an empty file": null
  },
  "spoken": {
    "L12 shown": "Line 12",
    "L30-L60 partial": "Lines 30–40",
    "L1000-L2000 shown": "Lines 1,000–2,000",
    "L60 not loaded": "No line anchored",
    "no anchor": "No line anchored"
  },
  "preferredView": {
    "README.md#L3-L4": "source",
    "README.md?plain=1": "source",
    "README.md?utm_source=chat&plain=1": "source",
    "README.md?plain=10": null,
    "README.md#install": null,
    "README.md": null
  },
  "lineAt": {
    "top of line 1": 1,
    "middle of line 3": 3,
    "below the last line": 40,
    "no line height": 0
  },
  "steps": [
    {
      "step": "open #L60 with lines 1–40 loaded",
      "address": "/view/src/app.py#L60",
      "gutter": "1–40",
      "value": "1 of 40: No line anchored",
      "status": "",
      "highlighted": null,
      "scrollTarget": null,
      "linePitch": null,
      "notice": {
        "role": "status",
        "text": "Line 60 is past the part of this file loaded so far (lines 1–40). Load more to reach it."
      },
      "scrolls": []
    },
    {
      "step": "Load more reaches line 60",
      "address": "/view/src/app.py#L60",
      "gutter": "1–100",
      "value": "60 of 100: Line 60",
      "status": "Line 60 highlighted.",
      "highlighted": "60–60",
      "scrollTarget": "present",
      "linePitch": "19.53125px",
      "notice": null,
      "scrolls": [
        {
          "line": 60,
          "block": "center",
          "inline": "nearest"
        }
      ],
      "appended": true
    },
    {
      "step": "click line 3",
      "address": "/view/src/app.py#L3",
      "gutter": "1–100",
      "value": "3 of 100: Line 3",
      "status": "Line 3 highlighted.",
      "highlighted": "3–3",
      "scrollTarget": "present",
      "linePitch": "19.53125px",
      "notice": null,
      "scrolls": []
    },
    {
      "step": "shift-click line 9",
      "address": "/view/src/app.py#L3-L9",
      "gutter": "1–100",
      "value": "9 of 100: Lines 3–9",
      "status": "Lines 3–9 highlighted.",
      "highlighted": "3–9",
      "scrollTarget": "present",
      "linePitch": "19.53125px",
      "notice": null,
      "scrolls": []
    },
    {
      "step": "shift-click line 1",
      "address": "/view/src/app.py#L1-L3",
      "gutter": "1–100",
      "value": "1 of 100: Lines 1–3",
      "status": "Lines 1–3 highlighted.",
      "highlighted": "1–3",
      "scrollTarget": "present",
      "linePitch": "19.53125px",
      "notice": null,
      "scrolls": []
    },
    {
      "step": "the reader edits the fragment to a reversed range",
      "address": "/view/src/app.py#L20-L10",
      "gutter": "1–100",
      "value": "10 of 100: Lines 10–20",
      "status": "Lines 10–20 highlighted.",
      "highlighted": "10–20",
      "scrollTarget": "present",
      "linePitch": "19.53125px",
      "notice": null,
      "scrolls": [
        {
          "line": 10,
          "block": "center",
          "inline": "nearest"
        }
      ]
    },
    {
      "step": "a column anchor",
      "address": "/view/src/app.py#L5C3-L7C9",
      "gutter": "1–100",
      "value": "5 of 100: Lines 5–7",
      "status": "Lines 5–7 highlighted.",
      "highlighted": "5–7",
      "scrollTarget": "present",
      "linePitch": "19.53125px",
      "notice": null,
      "scrolls": [
        {
          "line": 5,
          "block": "center",
          "inline": "nearest"
        }
      ]
    },
    {
      "step": "the zoom changes the rendered line height",
      "address": "/view/src/app.py#L5C3-L7C9",
      "gutter": "1–100",
      "value": "5 of 100: Lines 5–7",
      "status": "Lines 5–7 highlighted.",
      "highlighted": "5–7",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": []
    },
    {
      "step": "click line 90 at the new zoom",
      "address": "/view/src/app.py#L90",
      "gutter": "1–100",
      "value": "90 of 100: Line 90",
      "status": "Line 90 highlighted.",
      "highlighted": "90–90",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": []
    },
    {
      "step": "a line past the end",
      "address": "/view/src/app.py#L150",
      "gutter": "1–100",
      "value": "1 of 100: No line anchored",
      "status": "",
      "highlighted": null,
      "scrollTarget": null,
      "linePitch": "21.484375px",
      "notice": {
        "role": "status",
        "text": "Line 150 is past the end of this file, which has 100 lines."
      },
      "scrolls": []
    },
    {
      "step": "another file's fragment",
      "address": "/view/src/app.py#L150",
      "gutter": "1–100",
      "value": "1 of 100: No line anchored",
      "status": "",
      "highlighted": null,
      "scrollTarget": null,
      "linePitch": "21.484375px",
      "notice": {
        "role": "status",
        "text": "Line 150 is past the end of this file, which has 100 lines."
      },
      "scrolls": []
    },
    {
      "step": "the fragment is removed",
      "address": "/view/src/app.py",
      "gutter": "1–100",
      "value": "1 of 100: No line anchored",
      "status": "",
      "highlighted": null,
      "scrollTarget": null,
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": []
    },
    {
      "step": "open another file at #L70 with lines 1–40 loaded",
      "address": "/view/src/big.py#L70",
      "gutter": "1–40",
      "value": "1 of 40: No line anchored",
      "status": "",
      "highlighted": null,
      "scrollTarget": null,
      "linePitch": null,
      "notice": {
        "role": "status",
        "text": "Line 70 is past the part of this file loaded so far (lines 1–40). Load more to reach it."
      },
      "scrolls": []
    },
    {
      "step": "Load more renders the view again",
      "address": "/view/src/big.py#L70",
      "gutter": "1–100",
      "value": "70 of 100: Line 70",
      "status": "",
      "highlighted": "70–70",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 70,
          "block": "center",
          "inline": "nearest"
        }
      ]
    },
    {
      "step": "the refresh after that render",
      "address": "/view/src/big.py#L70",
      "gutter": "1–100",
      "value": "70 of 100: Line 70",
      "status": "",
      "highlighted": "70–70",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": []
    },
    {
      "step": "a task later, the status line speaks",
      "address": "/view/src/big.py#L70",
      "gutter": "1–100",
      "value": "70 of 100: Line 70",
      "status": "Line 70 highlighted.",
      "highlighted": "70–70",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": []
    },
    {
      "step": "Tab reaches the gutter",
      "address": "/view/src/big.py#L70",
      "gutter": "1–100",
      "value": "70 of 100: Line 70",
      "status": "Line 70 highlighted.",
      "highlighted": "70–70",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [],
      "role": "slider",
      "tabindex": "0",
      "label": "Line numbers",
      "orientation": "vertical"
    },
    {
      "step": "Down",
      "address": "/view/src/big.py#L71",
      "gutter": "1–100",
      "value": "71 of 100: Line 71",
      "status": "",
      "highlighted": "71–71",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 71,
          "block": "nearest",
          "inline": "nearest"
        }
      ],
      "prevented": true
    },
    {
      "step": "Shift+Down",
      "address": "/view/src/big.py#L71-L72",
      "gutter": "1–100",
      "value": "72 of 100: Lines 71–72",
      "status": "",
      "highlighted": "71–72",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 72,
          "block": "nearest",
          "inline": "nearest"
        }
      ],
      "prevented": true
    },
    {
      "step": "Shift+Up",
      "address": "/view/src/big.py#L71",
      "gutter": "1–100",
      "value": "71 of 100: Line 71",
      "status": "",
      "highlighted": "71–71",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 71,
          "block": "nearest",
          "inline": "nearest"
        }
      ],
      "prevented": true
    },
    {
      "step": "Shift+Up again",
      "address": "/view/src/big.py#L70-L71",
      "gutter": "1–100",
      "value": "70 of 100: Lines 70–71",
      "status": "",
      "highlighted": "70–71",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 70,
          "block": "nearest",
          "inline": "nearest"
        }
      ],
      "prevented": true
    },
    {
      "step": "Shift+Up across the fixed end",
      "address": "/view/src/big.py#L69-L71",
      "gutter": "1–100",
      "value": "69 of 100: Lines 69–71",
      "status": "",
      "highlighted": "69–71",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 69,
          "block": "nearest",
          "inline": "nearest"
        }
      ],
      "prevented": true
    },
    {
      "step": "Page Down",
      "address": "/view/src/big.py#L86",
      "gutter": "1–100",
      "value": "86 of 100: Line 86",
      "status": "",
      "highlighted": "86–86",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 86,
          "block": "nearest",
          "inline": "nearest"
        }
      ],
      "prevented": true
    },
    {
      "step": "End",
      "address": "/view/src/big.py#L100",
      "gutter": "1–100",
      "value": "100 of 100: Line 100",
      "status": "",
      "highlighted": "100–100",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 100,
          "block": "nearest",
          "inline": "nearest"
        }
      ],
      "prevented": true
    },
    {
      "step": "Home",
      "address": "/view/src/big.py#L1",
      "gutter": "1–100",
      "value": "1 of 100: Line 1",
      "status": "",
      "highlighted": "1–1",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 1,
          "block": "nearest",
          "inline": "nearest"
        }
      ],
      "prevented": true
    },
    {
      "step": "Shift+End",
      "address": "/view/src/big.py#L1-L100",
      "gutter": "1–100",
      "value": "100 of 100: Lines 1–100",
      "status": "",
      "highlighted": "1–100",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 100,
          "block": "nearest",
          "inline": "nearest"
        }
      ],
      "prevented": true
    },
    {
      "step": "Ctrl+Down, left to the browser",
      "address": "/view/src/big.py#L1-L100",
      "gutter": "1–100",
      "value": "100 of 100: Lines 1–100",
      "status": "",
      "highlighted": "1–100",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [],
      "prevented": false
    },
    {
      "step": "J, not a gutter key",
      "address": "/view/src/big.py#L1-L100",
      "gutter": "1–100",
      "value": "100 of 100: Lines 1–100",
      "status": "",
      "highlighted": "1–100",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [],
      "prevented": false
    },
    {
      "step": "focus leaves, and the reader edits the fragment",
      "address": "/view/src/big.py#L5",
      "gutter": "1–100",
      "value": "5 of 100: Line 5",
      "status": "Line 5 highlighted.",
      "highlighted": "5–5",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 5,
          "block": "center",
          "inline": "nearest"
        }
      ]
    },
    {
      "step": "a view rendered into the inert stage",
      "address": "/view/src/big.py#L5",
      "gutter": "1–100",
      "value": "5 of 100: Line 5",
      "status": "Line 5 highlighted.",
      "highlighted": "5–5",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": []
    },
    {
      "step": "a Source tab shown for the first time",
      "address": "/view/src/big.py#L5",
      "gutter": "1–100",
      "value": "5 of 100: Line 5",
      "status": "",
      "highlighted": "5–5",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 5,
          "block": "center",
          "inline": "nearest"
        }
      ]
    },
    {
      "step": "a task later, the status line speaks",
      "address": "/view/src/big.py#L5",
      "gutter": "1–100",
      "value": "5 of 100: Line 5",
      "status": "Line 5 highlighted.",
      "highlighted": "5–5",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": []
    },
    {
      "step": "a Markdown file with front matter at #L4-L5",
      "address": "/view/docs/guide.md#L4-L5",
      "gutter": "1–6",
      "value": "4 of 6: Lines 4–5",
      "status": "Lines 4–5 highlighted.",
      "highlighted": "4–5",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [
        {
          "line": 4,
          "block": "center",
          "inline": "nearest"
        }
      ],
      "parts": "2",
      "markdownParts": [
        {
          "className": "language-yaml",
          "text": "---\ntitle: Guide\n---\n",
          "lineOffset": "0"
        },
        {
          "className": "language-markdown",
          "text": "# Guide\n\nText.\n",
          "lineOffset": "3"
        }
      ],
      "copyPayloadIsTheText": true
    },
    {
      "step": "part of a Markdown file with front matter at #L4-L5",
      "address": "/view/docs/guide.md#L4-L5",
      "gutter": "1–4",
      "value": "4 of 4: Line 4",
      "status": "Line 4 highlighted.",
      "highlighted": "4–4",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": {
        "role": "status",
        "text": "Lines 4–5 continue past the part of this file loaded so far (lines 1–4). Load more to see the rest."
      },
      "scrolls": [
        {
          "line": 4,
          "block": "center",
          "inline": "nearest"
        }
      ],
      "markdownParts": [
        {
          "className": "language-markdown",
          "text": "---\ntitle: Guide\n---\n# Guide\n"
        }
      ]
    },
    {
      "step": "Load more appends the rest of the Markdown file",
      "address": "/view/docs/guide.md#L4-L5",
      "gutter": "1–6",
      "value": "4 of 6: Lines 4–5",
      "status": "Lines 4–5 highlighted.",
      "highlighted": "4–5",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": [],
      "appended": true,
      "markdownParts": [
        {
          "className": "language-markdown",
          "text": "---\ntitle: Guide\n---\n# Guide\n\nMore text.\n"
        }
      ]
    },
    {
      "step": "a Markdown file whose front matter never closes",
      "address": "/view/docs/guide.md#L4-L5",
      "gutter": "1–3",
      "value": "1 of 3: No line anchored",
      "status": "",
      "highlighted": null,
      "scrollTarget": null,
      "linePitch": null,
      "notice": {
        "role": "status",
        "text": "Lines 4–5 are past the end of this file, which has 3 lines."
      },
      "scrolls": [],
      "markdownParts": [
        "language-markdown"
      ]
    }
  ],
  "crlfLines": {
    "gutter": "1\n2\n3",
    "code": "one\ntwo\nthree\n"
  },
  "historyWrites": [
    "replace /view/src/app.py#L3",
    "replace /view/src/app.py#L3-L9",
    "replace /view/src/app.py#L1-L3",
    "replace /view/src/app.py#L90",
    "push /view/src/big.py#L70",
    "replace /view/src/big.py#L71",
    "replace /view/src/big.py#L71-L72",
    "replace /view/src/big.py#L71",
    "replace /view/src/big.py#L70-L71",
    "replace /view/src/big.py#L69-L71",
    "replace /view/src/big.py#L86",
    "replace /view/src/big.py#L100",
    "replace /view/src/big.py#L1",
    "replace /view/src/big.py#L1-L100",
    "push /view/docs/guide.md#L4-L5"
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
