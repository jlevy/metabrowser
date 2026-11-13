---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Shift Key Reveal and the Shell Keymap

Holding Shift alone outside a text field, past a short threshold, marks the root with
`data-key-reveal` and puts a keycap badge on every live shortcut target; the strip turns
to a second layer listing the common keys that are live.
A key the registry handles keeps the reveal and moves the badges, even when it moves
focus; any other key, a pointer press, a wheel, the window losing focus, a hidden page,
or a lost `keyup` ends it.
A capital or `?` typed within the threshold, Shift+wheel, Shift with the pointer
travelling, and Shift during a press never reveal.
The shell’s keys are targeted: each acts only while its control is on screen, so `U`
does nothing at the root and `Y` nothing on a folder, and a view tab’s letter follows
the bar the main pane commits, never one still staged.

This browserless session loads the production registry, `static/key-reveal.js`,
`static/shell-keymap.js`, Help with the real overlay layer, the file tree’s keys, Quick
Search, `static/main-tabs.js`, `static/pulls-nav.js`, and the filter bar’s dropdowns
from `static/filter-controls.js` whole, with injected time, pointer, and visibility.
Its stand-in DOM puts the window on every event’s path, as a browser does, so a capture
listener on the window hears an element’s `blur`. It plays the server’s side from
`tests/fixtures/key-reveal-responses.json`: the `/api/file`, `/api/git/repo`, and
`/api/source/status` answers of the in-process application, which
`tests/test_key_reveal_session.py` records and replays.
`tests/test_keymap.py` holds `shellKeys`, the keys each part’s registry registered for
the shell, to the reserved table in `src/metabrowser/keymap.py`. Each step records the
reveal’s state, whether the root is marked, the live keymap as key, command, and target,
the badges mounted, the strip’s surface and items, and Help’s groups; `did` is what the
shell’s stand-in activation paths were asked.
A `cost` is what one navigation or key cost: the registry’s publications, its liveness
reads of targets, and the keycaps built for badges and the strip.

## A Folder’s Files

The keymap of a plain folder: the file type filter’s menu, the root and a folder below
it, a Markdown file and a move to another of its kind, an agent log, structured data,
and HTML without active content, and the view tab letters following the committed bar
through a cancelled stage.

```console
$ node tests/dom/key-reveal-session.js
{
  "part": "keymap",
  "steps": [
    {
      "step": "a plain folder shows Files only",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "X opens the file type filter and focuses its checked row",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "pressed": {
        "key": "x",
        "handled": true
      },
      "focus": {
        "menu": "filter-type-menu",
        "row": "Any type",
        "checked": "true",
        "open": "true"
      },
      "did": ["opened the types menu"]
    },
    {
      "step": "↓ moves to the next row, and Escape closes the menu",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "next": {
        "menu": "filter-type-menu",
        "row": ".md",
        "checked": "false",
        "open": "true"
      },
      "did": ["closed the types menu"]
    },
    {
      "step": "a Markdown file has Document and Source",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "pressed": {
        "key": "s",
        "handled": true
      },
      "did": ["selected the source tab"]
    },
    {
      "step": "a move between two files of one kind registers nothing",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "cost": {
        "publications": ["batch(target)"],
        "targetReads": 0,
        "keycapsCreated": 0
      }
    },
    {
      "step": "a folder below the root has no Copy",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["U","header.parent","Open parent folder"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "pressed": {
        "key": "y",
        "handled": false
      }
    },
    {
      "step": "U opens the folder above",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["U","header.parent","Open parent folder"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "did": ["opened the folder \"\""]
    },
    {
      "step": "the root folder has no Up",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "pressed": {
        "key": "u",
        "handled": false
      }
    },
    {
      "step": "M shows the Treemap",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "did": ["selected the treemap tab"]
    },
    {
      "step": "an agent log has Log, Charts, and Raw JSON",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["L","view-tabs.l","Log tab"],
        ["C","view-tabs.c","Charts tab"],
        ["R","view-tabs.r","Raw JSON tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "R follows the committed bar, and a cancelled stage changes nothing",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["R","view-tabs.r","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "r": {
        "structured": "Tree",
        "agentLog": "Raw JSON",
        "back": "Tree",
        "whileStaged": "Tree",
        "afterCancel": "Tree"
      }
    },
    {
      "step": "an HTML file without active content has no tab keys",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","controls","filters","navigation","quick-file","help"]
    }
  ],
  "shellKeys": ["1","2","3","a","j","k","t","u","x","y"]
}
? 0
```

## Holding Shift

What reveals, what never does, and what ends a reveal; what a navigation and a key cost
while revealed; Quick Search’s field and Help; and the keymap after a `pageshow`
rebuild.

```console
$ node tests/dom/key-reveal-session.js gestures
{
  "part": "gestures",
  "steps": [
    {
      "step": "Shift held below the threshold shows nothing yet",
      "reveal": "armed",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "Shift held past the threshold reveals",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [
        ["1","Files tab"],
        ["A","Modified within"],
        ["X","File type"],
        ["U","beside, in file-header"],
        ["Y","beside, in file-header"],
        ["D","Document tab"],
        ["S","Source tab"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","1 Files","U Up","Y Copy"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "a navigation while revealed moves the badges in one pass",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["R","view-tabs.r","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [
        ["1","Files tab"],
        ["A","Modified within"],
        ["X","File type"],
        ["U","beside, in file-header"],
        ["Y","beside, in file-header"],
        ["R","Tree tab"],
        ["S","Source tab"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","1 Files","U Up","Y Copy"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "cost": {
        "publications": ["batch(target,registration)"],
        "targetReads": 10,
        "keycapsCreated": 12
      }
    },
    {
      "step": "releasing Shift puts everything back",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "a capital typed within the threshold never reveals",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "pressed": {
        "key": "Z",
        "handled": false
      }
    },
    {
      "step": "? within the threshold opens Help and never reveals",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["? or Esc","help.close",null]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "Shift+wheel never reveals",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "Shift with the pointer travelling to a click never reveals",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "a resting hand within the slop still reveals",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [
        ["1","Files tab"],
        ["A","Modified within"],
        ["X","File type"],
        ["U","beside, in file-header"],
        ["Y","beside, in file-header"],
        ["D","Document tab"],
        ["S","Source tab"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","1 Files","U Up","Y Copy"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "a pointer press while revealed dismisses it",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "Shift during a press that moved focus never reveals",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "focusedRow": "docs"
    },
    {
      "step": "↑ on a tree row moves one row and keeps the reveal",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "badges": [
        ["1","Files tab"],
        ["A","Modified within"],
        ["X","File type"],
        ["U","beside, in file-header"],
        ["Y","beside, in file-header"],
        ["D","Document tab"],
        ["S","Source tab"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","1 Files","U Up","Y Copy"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "pressed": {
        "key": "ArrowUp",
        "handled": true
      },
      "focusedRow": "README.md",
      "cost": {
        "publications": ["dispatch"],
        "targetReads": 10,
        "keycapsCreated": 6
      },
      "did": ["the tree opened README.md"]
    },
    {
      "step": "a held J moves rows and does no reveal work on its repeats",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "badges": [
        ["1","Files tab"],
        ["A","Modified within"],
        ["X","File type"],
        ["U","beside, in file-header"],
        ["Y","beside, in file-header"],
        ["D","Document tab"],
        ["S","Source tab"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","1 Files","U Up","Y Copy"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "focusedRow": "docs",
      "repeats": {
        "publications": [],
        "targetReads": 0,
        "keycapsCreated": 0
      },
      "did": ["the tree opened data.json","the tree opened docs"]
    },
    {
      "step": "the window losing focus ends the reveal",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "a key without Shift ends a reveal whose keyup was lost",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "the page going hidden ends the reveal",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "Shift in Quick Search's field never reveals",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["↑","quick-file.previous",null],
        ["↓","quick-file.next",null],
        ["Enter","quick-file.activate",null],
        ["Esc","quick-file.close",null]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "focus": "combobox"
    },
    {
      "step": "with Help open only Help's keys are live",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["? or Esc","help.close",null]
      ],
      "badges": [],
      "strip": {
        "surface": "reveal",
        "items": []
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "the keymap after a pageshow rebuild",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["D","view-tabs.d","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "sameAsBefore": true
    }
  ],
  "shellKeys": ["1","2","3","a","j","k","t","u","x","y"]
}
? 0
```

## The Main Tabs, a Commit, a Stack, and a Pin

`2` and `1` under a held Shift, a commit view’s Copy revision, Commits registered while
the registry is down, Pulls drawn before Git discovery, the Preview tab’s `P` beside the
stack’s, a pull request in and outside a stack, and a mirror’s pin with its branch
switcher and no modified-within filter.

```console
$ node tests/dom/key-reveal-session.js tabs
{
  "part": "tabs",
  "steps": [
    {
      "step": "a Git repository shows Files and Commits",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "2 with Shift still held opens Commits, focuses its row, and keeps the reveal",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"]
      ],
      "badges": [
        ["1","Files tab"],
        ["2","Commits tab"],
        ["O","Overview tab"],
        ["M","Treemap tab"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","1 Files","2 Commits"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "pressed": {
        "key": "2",
        "handled": true
      },
      "active": "git",
      "focus": "a1",
      "did": ["address /view/"]
    },
    {
      "step": "1 during the reveal shows the filter bar, and X and A gain badges",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "badges": [
        ["1","Files tab"],
        ["2","Commits tab"],
        ["A","Modified within"],
        ["X","File type"],
        ["O","Overview tab"],
        ["M","Treemap tab"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","1 Files","2 Commits"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "pressed": {
        "key": "1",
        "handled": true
      },
      "active": "files",
      "focus": "README.md"
    },
    {
      "step": "releasing Shift ends the reveal",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"]
    },
    {
      "step": "J on a commit row ends the reveal, since the row handles it itself",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "did": ["address /view/","the commit row moved down from a1"]
    },
    {
      "step": "a commit view's Y copies its revision",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["Y","header.copy","Copy revision"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","controls","filters","navigation","quick-file","help"],
      "pressed": {
        "key": "y",
        "handled": true
      },
      "did": ["copied 0123456789abcdef0123456789abcdef01234567"]
    },
    {
      "step": "Commits registered while the registry is down gets its tab, then its key",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "whileDown": {
        "threw": null,
        "tab": true,
        "container": true,
        "key": null
      },
      "key": "2",
      "pressed": {
        "key": "2",
        "handled": true
      },
      "active": "git",
      "did": ["address /view/"]
    },
    {
      "step": "Pulls drawn before Commits keeps 3, and 2 stays reserved",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["3","main-tabs.pulls","Pulls tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","pull-requests","pull-stack","quick-file","help"],
      "pressed": {
        "key": "2",
        "handled": false
      }
    },
    {
      "step": "a repository with a hosted origin shows Files, Commits, and Pulls",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["3","main-tabs.pulls","Pulls tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","pull-requests","pull-stack","quick-file","help"]
    },
    {
      "step": "the Preview tab's P sits beside the stack's P",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["3","main-tabs.pulls","Pulls tab"],
        ["P","view-tabs.p","Preview tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"],
        ["X","filter.type","File type"],
        ["A","filter.recency","Modified within"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","pull-requests","pull-stack","quick-file","help"],
      "pressed": {
        "key": "p",
        "handled": true
      },
      "did": ["selected the preview tab"]
    },
    {
      "step": "3 again, once the list has rows, moves focus to the selected row",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["3","main-tabs.pulls","Pulls tab"],
        ["P","view-tabs.p","Preview tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","/ crumb"],
        ["Y","header.copy","Copy path"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","pull-requests","pull-stack","quick-file","help"],
      "pressed": {
        "key": "3",
        "handled": true
      },
      "focus": "#7",
      "did": ["address /pulls"]
    },
    {
      "step": "a pull request outside a stack has no N or P",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["3","main-tabs.pulls","Pulls tab"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","controls","filters","navigation","pull-requests","pull-stack","quick-file","help"],
      "focus": "#7",
      "pressed": {
        "key": "n",
        "handled": false
      }
    },
    {
      "step": "a pull request in a stack lists N or P on the strip",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["3","main-tabs.pulls","Pulls tab"],
        ["N","pulls.stack.top",null],
        ["P","pulls.stack.base",null]
      ],
      "badges": [
        ["1","Files tab"],
        ["2","Commits tab"],
        ["3","Pulls tab"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","1 Files","2 Commits","3 Pulls","N or P Stack"]
      },
      "help": ["anywhere","main-tabs","controls","filters","navigation","pull-requests","pull-stack","quick-file","help"],
      "pressed": {
        "key": "n",
        "handled": true
      },
      "did": ["moved toward the stack's top"]
    },
    {
      "step": "P walks the stack toward its base",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["2","main-tabs.git","Commits tab"],
        ["3","main-tabs.pulls","Pulls tab"],
        ["N","pulls.stack.top",null],
        ["P","pulls.stack.base",null]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","controls","filters","navigation","pull-requests","pull-stack","quick-file","help"],
      "pressed": {
        "key": "p",
        "handled": true
      },
      "did": ["moved toward its base"]
    },
    {
      "step": "a mirror's pin has W and no A",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["1","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["W","source.switch-ref","Branch: topic"],
        ["X","filter.type","File type"]
      ],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","filters","navigation","quick-file","help"],
      "pressed": {
        "key": "w",
        "handled": true
      },
      "a": false,
      "did": ["opened the branch list and focused its filter"]
    }
  ],
  "shellKeys": ["1","2","3","a","j","k","n","p","t","u","w","x","y"]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
