---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Diff’s File Type Filter

A multi-file diff leads its layout control with the Files tab’s **File type** menu:
**Any type**, then the Groups and each display group’s families with the files they
count, then the extensions most numerous first.
The counts are the comparison route’s `view=types` answer, asked for as the diff mounts,
and which files a choice keeps is the route’s `types=` answer
(`cli-api-diff-type-filter.tryscript.md` pins both).
A choice paints at once, so the menu shows it while its files load, and the control is
busy until they do; their answer then mounts in place of the diff before it, and the
toolbar says how many of the comparison’s files it keeps, with **Clear**. One set of
types is one address whatever order it was picked in, an answer a later choice overtook
is dropped, and going back to **Any type** mounts the whole comparison it kept, asking
for nothing. A choice that keeps no file says so, and one whose files do not load says
that and keeps the diff it had.
**Clear** gives focus to the menu’s trigger, since it is gone once nothing is chosen.
`Y` opens the menu with its checked row focused, through the SDK’s shortcut surface, and
its target follows each repaint.
The handle a host holds goes to whichever diff is mounted, and its current-file listener
is carried from each diff to the next.

This browserless session loads the production `builtin_plugins/diff/diff-type-filter.js`
with `static/filter-controls.js`, whose menu rows and markup the control draws.
The route is a stand-in that answers when the session says, and a mount is a stand-in
that records the files it was given.
It asserts, and so prints nothing for, that exactly one diff is mounted after every
step, that no replaced diff keeps the host’s listener, and that disposing aborts a
request still running, disposes the diff, detaches `Y`, and unbinds the control.

```console
$ node tests/dom/diff-type-filter-session.js
{
  "steps": [
    {
      "step": "mounted: the whole comparison, counts asked for",
      "requests": [
        "view=types"
      ],
      "mounted": [
        "README.md",
        "docs/guide.md",
        "src/app.py",
        "src/util.py",
        "web/app.js",
        "logo.png"
      ],
      "control": {
        "trigger": "Any type",
        "note": null,
        "clear": false,
        "busy": false
      }
    },
    {
      "step": "the counts arrive",
      "requests": [],
      "mounted": [
        "README.md",
        "docs/guide.md",
        "src/app.py",
        "src/util.py",
        "web/app.js",
        "logo.png"
      ],
      "control": {
        "trigger": "Any type",
        "note": null,
        "clear": false,
        "busy": false
      }
    },
    {
      "step": "the menu opens",
      "requests": [],
      "mounted": [
        "README.md",
        "docs/guide.md",
        "src/app.py",
        "src/util.py",
        "web/app.js",
        "logo.png"
      ],
      "control": {
        "trigger": "Any type",
        "rows": [
          "[x] Any type",
          "— Groups",
          "[ ] Documentation 2",
          "[ ] Code 3",
          "— Documentation",
          "[ ] Markdown 2",
          "— Code",
          "[ ] Python 2",
          "[ ] JavaScript 1",
          "[ ] .md 2",
          "[ ] .py 2",
          "[ ] .js 1",
          "[ ] .png 1"
        ],
        "note": null,
        "clear": false,
        "busy": false
      }
    },
    {
      "step": "Markdown chosen: asked for, the menu shows the choice while it loads",
      "requests": [
        "types=.md"
      ],
      "mounted": [
        "README.md",
        "docs/guide.md",
        "src/app.py",
        "src/util.py",
        "web/app.js",
        "logo.png"
      ],
      "control": {
        "trigger": "Markdown",
        "rows": [
          "[ ] Any type",
          "— Groups",
          "[ ] Documentation 2",
          "[ ] Code 3",
          "— Documentation",
          "[x] Markdown 2",
          "— Code",
          "[ ] Python 2",
          "[ ] JavaScript 1",
          "[x] .md 2",
          "[ ] .py 2",
          "[ ] .js 1",
          "[ ] .png 1"
        ],
        "note": null,
        "clear": true,
        "busy": true
      }
    },
    {
      "step": "its answer mounts in place of the whole",
      "requests": [],
      "mounted": [
        "README.md",
        "docs/guide.md"
      ],
      "narrowed": {
        "kept": 2,
        "whole": 6
      },
      "control": {
        "trigger": "Markdown",
        "rows": [
          "[ ] Any type",
          "— Groups",
          "[ ] Documentation 2",
          "[ ] Code 3",
          "— Documentation",
          "[x] Markdown 2",
          "— Code",
          "[ ] Python 2",
          "[ ] JavaScript 1",
          "[x] .md 2",
          "[ ] .py 2",
          "[ ] .js 1",
          "[ ] .png 1"
        ],
        "note": "2 of 6 files",
        "clear": true,
        "busy": false
      }
    },
    {
      "step": "Python added: one address for the set, sorted",
      "requests": [
        "types=.md,.py"
      ],
      "mounted": [
        "README.md",
        "docs/guide.md"
      ],
      "narrowed": {
        "kept": 2,
        "whole": 6
      },
      "control": {
        "trigger": ".md +1",
        "rows": [
          "[ ] Any type",
          "— Groups",
          "[ ] Documentation 2",
          "[ ] Code 3",
          "— Documentation",
          "[x] Markdown 2",
          "— Code",
          "[x] Python 2",
          "[ ] JavaScript 1",
          "[x] .md 2",
          "[x] .py 2",
          "[ ] .js 1",
          "[ ] .png 1"
        ],
        "note": "2 of 6 files",
        "clear": true,
        "busy": true
      }
    },
    {
      "step": "the two types' files",
      "requests": [],
      "mounted": [
        "README.md",
        "docs/guide.md",
        "src/app.py",
        "src/util.py"
      ],
      "narrowed": {
        "kept": 4,
        "whole": 6
      },
      "control": {
        "trigger": ".md +1",
        "rows": [
          "[ ] Any type",
          "— Groups",
          "[ ] Documentation 2",
          "[ ] Code 3",
          "— Documentation",
          "[x] Markdown 2",
          "— Code",
          "[x] Python 2",
          "[ ] JavaScript 1",
          "[x] .md 2",
          "[x] .py 2",
          "[ ] .js 1",
          "[ ] .png 1"
        ],
        "note": "4 of 6 files",
        "clear": true,
        "busy": false
      }
    },
    {
      "step": "Markdown off, then JavaScript on before the first answer",
      "requests": [
        "types=.py (dropped)",
        "types=.js,.py"
      ],
      "mounted": [
        "README.md",
        "docs/guide.md",
        "src/app.py",
        "src/util.py"
      ],
      "narrowed": {
        "kept": 4,
        "whole": 6
      },
      "control": {
        "trigger": "Code",
        "rows": [
          "[ ] Any type",
          "— Groups",
          "[ ] Documentation 2",
          "[x] Code 3",
          "— Documentation",
          "[ ] Markdown 2",
          "— Code",
          "[x] Python 2",
          "[x] JavaScript 1",
          "[ ] .md 2",
          "[x] .py 2",
          "[x] .js 1",
          "[ ] .png 1"
        ],
        "note": "4 of 6 files",
        "clear": true,
        "busy": true
      }
    },
    {
      "step": "the overtaken answer arrives last and is dropped",
      "requests": [],
      "mounted": [
        "src/app.py",
        "src/util.py",
        "web/app.js"
      ],
      "narrowed": {
        "kept": 3,
        "whole": 6
      },
      "control": {
        "trigger": "Code",
        "rows": [
          "[ ] Any type",
          "— Groups",
          "[ ] Documentation 2",
          "[x] Code 3",
          "— Documentation",
          "[ ] Markdown 2",
          "— Code",
          "[x] Python 2",
          "[x] JavaScript 1",
          "[ ] .md 2",
          "[x] .py 2",
          "[x] .js 1",
          "[ ] .png 1"
        ],
        "note": "3 of 6 files",
        "clear": true,
        "busy": false
      }
    },
    {
      "step": "Code turned off, Documentation turned on",
      "requests": [
        "types=.md,readme"
      ],
      "mounted": [
        "README.md",
        "docs/guide.md",
        "src/app.py",
        "src/util.py",
        "web/app.js",
        "logo.png"
      ],
      "control": {
        "trigger": "Documentation",
        "rows": [
          "[ ] Any type",
          "— Groups",
          "[x] Documentation 2",
          "[ ] Code 3",
          "— Documentation",
          "[x] Markdown 2",
          "— Code",
          "[ ] Python 2",
          "[ ] JavaScript 1",
          "[x] .md 2",
          "[ ] .py 2",
          "[ ] .js 1",
          "[ ] .png 1"
        ],
        "note": null,
        "clear": true,
        "busy": true
      }
    },
    {
      "step": "Documentation's files",
      "requests": [],
      "mounted": [
        "README.md",
        "docs/guide.md"
      ],
      "narrowed": {
        "kept": 2,
        "whole": 6
      },
      "control": {
        "trigger": "Documentation",
        "rows": [
          "[ ] Any type",
          "— Groups",
          "[x] Documentation 2",
          "[ ] Code 3",
          "— Documentation",
          "[x] Markdown 2",
          "— Code",
          "[ ] Python 2",
          "[ ] JavaScript 1",
          "[x] .md 2",
          "[ ] .py 2",
          "[ ] .js 1",
          "[ ] .png 1"
        ],
        "note": "2 of 6 files",
        "clear": true,
        "busy": false
      }
    },
    {
      "step": "Any type: the whole comparison again, nothing asked",
      "requests": [],
      "mounted": [
        "README.md",
        "docs/guide.md",
        "src/app.py",
        "src/util.py",
        "web/app.js",
        "logo.png"
      ],
      "control": {
        "trigger": "Any type",
        "rows": [
          "[x] Any type",
          "— Groups",
          "[ ] Documentation 2",
          "[ ] Code 3",
          "— Documentation",
          "[ ] Markdown 2",
          "— Code",
          "[ ] Python 2",
          "[ ] JavaScript 1",
          "[ ] .md 2",
          "[ ] .py 2",
          "[ ] .js 1",
          "[ ] .png 1"
        ],
        "note": null,
        "clear": false,
        "busy": false
      }
    },
    {
      "step": "a type with no changed file",
      "requests": [
        "types=.rs"
      ],
      "mounted": [],
      "narrowed": {
        "kept": 0,
        "whole": 6
      },
      "control": {
        "trigger": "Any type",
        "rows": [
          "[ ] Any type",
          "— Groups",
          "[ ] Documentation 2",
          "[ ] Code 3",
          "— Documentation",
          "[ ] Markdown 2",
          "— Code",
          "[ ] Python 2",
          "[ ] JavaScript 1",
          "[ ] .md 2",
          "[ ] .py 2",
          "[ ] .js 1",
          "[ ] .png 1"
        ],
        "note": "0 of 6 files",
        "clear": true,
        "busy": false
      }
    },
    {
      "step": "a choice whose files do not load keeps the diff it had",
      "requests": [
        "types=.png,.rs"
      ],
      "mounted": [],
      "narrowed": {
        "kept": 0,
        "whole": 6
      },
      "control": {
        "trigger": ".png",
        "rows": [
          "[ ] Any type",
          "— Groups",
          "[ ] Documentation 2",
          "[ ] Code 3",
          "— Documentation",
          "[ ] Markdown 2",
          "— Code",
          "[ ] Python 2",
          "[ ] JavaScript 1",
          "[ ] .md 2",
          "[ ] .py 2",
          "[ ] .js 1",
          "[x] .png 1"
        ],
        "note": "Could not load the files of these types.",
        "clear": true,
        "busy": false
      }
    },
    {
      "step": "Clear",
      "requests": [],
      "mounted": [
        "README.md",
        "docs/guide.md",
        "src/app.py",
        "src/util.py",
        "web/app.js",
        "logo.png"
      ],
      "control": {
        "trigger": "Any type",
        "note": null,
        "clear": false,
        "busy": false
      }
    },
    {
      "step": "Y opens the menu",
      "requests": [],
      "mounted": [
        "README.md",
        "docs/guide.md",
        "src/app.py",
        "src/util.py",
        "web/app.js",
        "logo.png"
      ],
      "control": {
        "trigger": "Any type",
        "rows": [
          "[x] Any type",
          "— Groups",
          "[ ] Documentation 2",
          "[ ] Code 3",
          "— Documentation",
          "[ ] Markdown 2",
          "— Code",
          "[ ] Python 2",
          "[ ] JavaScript 1",
          "[ ] .md 2",
          "[ ] .py 2",
          "[ ] .js 1",
          "[ ] .png 1"
        ],
        "note": null,
        "clear": false,
        "busy": false
      }
    }
  ],
  "hostListener": [
    "README.md",
    "README.md",
    "README.md",
    "src/app.py",
    "README.md",
    "README.md",
    "README.md",
    null,
    "README.md"
  ],
  "reports": [
    "files"
  ],
  "key": {
    "id": "diff.type-filter",
    "key": "y",
    "group": "controls",
    "copy": {
      "action": "Choose file types",
      "description": "Open the diff's File type menu.",
      "hint": "File type"
    },
    "retargetedOnRepaint": true
  },
  "disposed": {
    "pendingRequest": "aborted",
    "diffs": "disposed",
    "key": "detached"
  },
  "params": [
    ".md,.py",
    null,
    null
  ],
  "notes": [
    "4 of 35 files",
    "0 of 1 file",
    "1,234 of 5,678 files"
  ],
  "none": "No changed file is of the chosen types."
}
? 0
```
