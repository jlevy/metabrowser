---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Source Ref Selector Keys

The branch switcher’s open list leaves every key held with Command, Control, or Option
to the browser, so Command-R reloads and Command-Left goes back with the list open.
Its two listeners are the document’s, which closes the list on Escape and keeps Tab
inside it, and the panel’s, which moves among the rows on the arrows, Home, and End.
Neither takes a chord: the session presses each key they handle, and `r`, with Command,
Shift-Command, Control, and Option from the filter, from a row, and from the kind tab,
and fails if one is taken, closes the list, or moves focus.
Option-Tab is the one chord the list keeps, since Safari moves focus with it.
The plain keys still work: `↓` from the filter reaches the first row, Tab and Option-Tab
wrap from the last stop, and Escape closes the list and returns focus to its button.

`workingTreeTab` is a checkout’s chooser on a page that shows a branch.
An arrow key onto the **Working tree** tab shows the tab and asks for its listing, and
asks the pin route nothing; a press on the tab, which a pointer’s click and Enter or
Space on it both are, asks the pin route for the working tree, once.
`refresh` is a press on the navigation’s Refresh with the list open: the one press
beside the list that leaves it open, since Refresh reads it again, after which the row
that had focus has it back, while a press anywhere else closes the list.

This browserless session loads the production `static/filter-controls.js` and
`static/source-ref-selector.js` on the stand-in DOM of `tests/dom/key-reveal-dom.js`,
mounts the selector as the shell does, and answers its listing with the recorded
branches from `tests/fixtures/source-ref-selector-responses.json`.

```console
$ node tests/dom/source-ref-selector-keys-session.js
{
  "opened": {
    "open": true,
    "focus": "the filter",
    "requests": [
      "/api/source/refs?kind=branch"
    ],
    "rows": [
      "the row refs/remotes/origin/topic",
      "the row refs/remotes/origin/feature"
    ]
  },
  "chords": [
    "Command",
    "Shift-Command",
    "Control",
    "Option"
  ],
  "chorded": [
    {
      "place": "the filter",
      "focus": "the filter",
      "presses": 27,
      "taken": [],
      "listOpen": true,
      "focusMoved": null
    },
    {
      "place": "a row",
      "focus": "the row refs/remotes/origin/feature",
      "presses": 27,
      "taken": [],
      "listOpen": true,
      "focusMoved": null
    },
    {
      "place": "the kind tab",
      "focus": "Branches",
      "presses": 27,
      "taken": [],
      "listOpen": true,
      "focusMoved": null
    }
  ],
  "plain": [
    {
      "key": "ArrowDown from the filter",
      "taken": true,
      "focus": "the row refs/remotes/origin/topic",
      "listOpen": true
    },
    {
      "key": "Tab from the row refs/remotes/origin/feature",
      "taken": true,
      "focus": "Branches",
      "listOpen": true
    },
    {
      "key": "Option-Tab from the row refs/remotes/origin/feature",
      "taken": true,
      "focus": "Branches",
      "listOpen": true
    },
    {
      "key": "Escape from the row refs/remotes/origin/topic",
      "taken": true,
      "focus": "Switch branch or tag",
      "listOpen": false
    }
  ],
  "workingTreeTab": {
    "opened": {
      "tabs": [
        "Working tree",
        "Branches (shown)",
        "Remotes",
        "Tags"
      ],
      "focus": "the filter"
    },
    "arrowed": {
      "tabs": [
        "Working tree (shown)",
        "Branches",
        "Remotes",
        "Tags"
      ],
      "focus": "Working tree",
      "requests": [
        "/api/source/refs?kind=working_tree"
      ]
    },
    "pressed": {
      "requests": [
        "POST /api/source/pin {\"working_tree\":true,\"view\":\"/view/\"}"
      ]
    },
    "refresh": {
      "after": {
        "listOpen": true,
        "requests": [
          "/api/source/refs?kind=branch"
        ],
        "focus": "the row refs/remotes/origin/feature"
      },
      "pressedElsewhere": {
        "listOpen": false
      }
    }
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
