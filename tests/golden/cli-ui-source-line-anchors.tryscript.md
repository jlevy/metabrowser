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
      "highlighted": "70–70",
      "scrollTarget": "present",
      "linePitch": "21.484375px",
      "notice": null,
      "scrolls": []
    },
    {
      "step": "the refresh after that render",
      "address": "/view/src/big.py#L70",
      "gutter": "1–100",
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
    "push /view/src/big.py#L70"
  ]
}
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
