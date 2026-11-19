---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Command, Control, and Option Are the Browser’s

Every chord is left to the browser and the platform, so Command-R reloads wherever focus
is: on the page, on a tree row, in Quick Search’s field, in Help, in an open filter
menu, and in Group by’s open menu, whose rows have letters.
The registry’s two Control chords, Control-N and Control-P, are the exception on a pull
request in a stack on a Mac, the session’s navigator, where they walk the stack and are
the only chords taken; Quick Search’s field keeps them there too.
In each place the session presses every letter, digit, and named key with Command,
Shift-Command, Control, and Option, and fails if a chord other than those is taken, runs
a command, or moves focus.
`presses` counts them; Option-Tab is left out, since a modal’s focus trap keeps it for
Safari, which moves focus with it.

```console
$ node tests/dom/key-reveal-session.js modified
{
  "part": "modified",
  "chords": ["Command","Shift-Command","Control","Option"],
  "keys": 50,
  "steps": [
    {
      "place": "the page",
      "focus": "body",
      "presses": 199,
      "commandR": "left to the browser",
      "taken": [],
      "did": [],
      "focusMoved": null
    },
    {
      "place": "a tree row",
      "focus": "README.md",
      "presses": 199,
      "commandR": "left to the browser",
      "taken": [],
      "did": [],
      "focusMoved": null
    },
    {
      "place": "Quick Search's field",
      "focus": "Find a known file",
      "presses": 199,
      "commandR": "left to the browser",
      "taken": [],
      "did": [],
      "focusMoved": null
    },
    {
      "place": "Help",
      "focus": "Close Help",
      "presses": 199,
      "commandR": "left to the browser",
      "taken": [],
      "did": [],
      "focusMoved": null
    },
    {
      "place": "the file type filter's open menu",
      "focus": "Any type row",
      "presses": 199,
      "commandR": "left to the browser",
      "taken": [],
      "did": [],
      "focusMoved": null
    },
    {
      "place": "the Group by menu, whose rows have letters",
      "focus": "No grouping row",
      "presses": 199,
      "commandR": "left to the browser",
      "taken": [],
      "did": [],
      "focusMoved": null
    },
    {
      "place": "a pull request in a stack",
      "focus": "body",
      "presses": 199,
      "commandR": "left to the browser",
      "taken": ["Control-n","Control-p"],
      "did": ["moved toward the stack's top","moved toward its base"],
      "focusMoved": null
    },
    {
      "place": "Quick Search's field on a pull request in a stack",
      "focus": "Find a known file",
      "presses": 199,
      "commandR": "left to the browser",
      "taken": [],
      "did": [],
      "focusMoved": null
    }
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
