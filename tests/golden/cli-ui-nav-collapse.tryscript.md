---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Hiding the Navigation Pane

Backslash hides the navigation pane from anywhere outside a text field, through the
chevron’s own path, and Shift-Backslash, which types `|` on a US keyboard, shows it
again, since `|` is the Backslash key’s Shift form (docs/design-system.md, “Hiding the
Navigation Pane”). The session runs the production shortcut registry, shell keymap, and
`static/nav-collapse.js` on the key reveal session’s stand-in shell.

Hidden, the pane is inert, so the keys of its controls, `0`, `F`, and the filters’
numbers, leave the live keymap, and focus on a tree row moves to the main page.
Backslash stays live on the chevron, which the main frame holds, and its label says what
it does next. Shown again, the pane’s keys come back.

The frame’s slide takes `--motion-reveal`’s time and easing, which the session reads
from `styles.css`, and the session finishes each slide as time would.
The pane is live as a show starts and takes its place in the layout when it ends.
A second press halfway through a slide turns it back from where the frame is, for half
the time.

The page holds a reading column, which the stylesheet centers in the frame while the
pane is out of the layout (`--reading-inset`; the stand-in sets 415 px as it would).
The column glides by the inset’s change over the slide’s own time rather than jumping
with the layout: a hide starts it where it was drawn, 415 px back, and brings it to
rest; a show takes it 415 px toward the frame’s start and holds it there until the slide
ends and the layout puts it back.
A turned slide picks the glide up where it is drawn.
The key in the same place on a UK or German keyboard types `#`, which is not Backslash.
Hiding the pane closes a filter menu it held open.

`cli-ui-key-reveal.tryscript.md` shows the key live on every screen and its badge beside
the chevron; `tests/test_nav_collapse_chrome.py` measures the slide in headless Chrome.

```console
$ node tests/dom/nav-collapse-session.js
{
  "part": "nav",
  "steps": [
    {
      "step": "a file is open with the navigation pane shown",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "nav": {
        "inert": false,
        "inLayout": true,
        "expanded": "true",
        "label": "Hide navigation"
      }
    },
    {
      "step": "\\ hides the navigation pane, and only the main page's keys stay live",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["\\","shell.nav-toggle","Show navigation"],
        ["V","view-tabs.v","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"]
      ],
      "numbers": [],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "\\",
        "handled": true
      },
      "slide": {
        "from": 300,
        "to": 0,
        "duration": 180,
        "easing": "cubic-bezier(0.2, 0, 0, 1)",
        "cancelled": 0,
        "glide": {
          "from": -415,
          "to": 0,
          "duration": 180,
          "fill": "none",
          "cancelled": 0
        }
      },
      "nav": {
        "inert": true,
        "inLayout": false,
        "expanded": "false",
        "label": "Show navigation",
        "focus": "preview-pane"
      },
      "did": ["hid the navigation pane"]
    },
    {
      "step": "Shift-\\, which types | on a US keyboard, shows it again",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "|",
        "handled": true
      },
      "sliding": {
        "slide": {
          "from": 0,
          "to": 300,
          "duration": 180,
          "easing": "cubic-bezier(0.2, 0, 0, 1)",
          "cancelled": 0,
          "glide": {
            "from": 0,
            "to": -415,
            "duration": 180,
            "fill": "forwards",
            "cancelled": 0
          }
        },
        "nav": {
          "inert": false,
          "inLayout": false,
          "expanded": "true",
          "label": "Hide navigation"
        }
      },
      "nav": {
        "inert": false,
        "inLayout": true,
        "expanded": "true",
        "label": "Hide navigation"
      },
      "did": ["showed the navigation pane"]
    },
    {
      "step": "# on the key US keyboards have \\ on is not \\",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "#",
        "handled": false
      },
      "slide": null,
      "nav": {
        "inert": false,
        "inLayout": true,
        "expanded": "true",
        "label": "Hide navigation"
      }
    },
    {
      "step": "\\ again halfway through the slide turns it back from there",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "\\",
        "handled": true
      },
      "slide": {
        "from": 150,
        "to": 300,
        "duration": 90,
        "easing": "cubic-bezier(0.2, 0, 0, 1)",
        "cancelled": 1,
        "glide": {
          "from": -207.5,
          "to": -415,
          "duration": 90,
          "fill": "forwards",
          "cancelled": 1
        }
      },
      "nav": {
        "inert": false,
        "inLayout": true,
        "expanded": "true",
        "label": "Hide navigation"
      },
      "did": ["hid the navigation pane","showed the navigation pane"]
    },
    {
      "step": "\\ with Group by open closes the menu as it hides the pane",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["\\","shell.nav-toggle","Show navigation"],
        ["V","view-tabs.v","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"]
      ],
      "numbers": [],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "\\",
        "handled": true
      },
      "menu": {
        "before": "group",
        "after": null
      },
      "nav": {
        "inert": true,
        "inLayout": false,
        "expanded": "false",
        "label": "Show navigation",
        "focus": "preview-pane"
      },
      "did": ["opened the group menu","closed the group menu","hid the navigation pane"]
    }
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
