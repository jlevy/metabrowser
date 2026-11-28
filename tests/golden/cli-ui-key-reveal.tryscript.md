---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Shift Key Reveal and the Shell Keymap

Holding Shift alone outside a text field, past a short threshold, marks the root with
`data-key-reveal` and puts a keycap badge on every live shortcut target; the strip,
which at rest is one row that lists Shift first, as Reveal keys, ahead of `?` for Help,
turns to a second layer listing the common keys that are live.
`cli-ui-shortcut-strip.tryscript.md` shows that row in a narrowing and a widening pane.
A key the registry handles keeps the reveal and moves the badges, even when it moves
focus; any other key, a pointer press, a wheel, the window losing focus, a hidden page,
or a lost `keyup` ends it.
A capital or `?` typed within the threshold, Shift+wheel, Shift with the pointer
travelling, and Shift during a press never reveal.
The shell’s keys are targeted: each acts only while its control is on screen, so `U`
does nothing at the root, and a view tab’s letter follows the bar the main pane commits,
never one still staged.
Letters name known meanings, as “Keyboard Shortcuts” in `docs/design-system.md` sets
out: `F`, `P`, and `H` for the Files, Pulls, and Commits tabs, `V` and `S` for a file’s
rendered view and its source, and Control-N and Control-P for the next and previous item
one level up. The filters are situational, so they take numbers from the registry’s one
numbering, 1 to 9 in reading order: `numbers` lists what each number reaches, the first
being 1. An open menu’s rows take the letters they declare, in the menu’s own scope and
only while it has focus: in Group by’s, `T` chooses By file type, and the revealed strip
offers Quick Search by `/` alone.
Copying is ancillary, so no copy control carries a key, and Help lists the numbers as
one positional row and gives one digit a fixed meaning, `0`, Home, which the folder’s
name badges and which goes home on any screen, with Shift too; the session fails if
either breaks.

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
the shell, to the reserved table in `src/metabrowser/keymap.py`, and `shellCommands`,
each shell letter and Control chord with the command it is bound to and that command’s
Help action, to the meanings the design system’s keymap table gives those letters.
Each step records the reveal’s state, whether the root is marked, the live keymap as
key, command, and target, the badges mounted, the strip’s surface and items, and Help’s
groups; `did` is what the shell’s stand-in activation paths were asked.
A `cost` is what one navigation or key cost: the registry’s publications, its liveness
reads of targets, and the keycaps built for badges and the strip.

## A Folder’s Files

The keymap of a plain folder: the file type filter’s number and menu; where focus lands
for each way a filter menu opens, on its checked row, and closes, on its trigger, and
through a pick and a rebuild; Group by’s menu and its rows’ letters, N, A, and T, which
are live only while it is open and has focus and which Help lists under Menus; the root
and a folder below it, a Markdown file and a move to another of its kind, its Copy path
with no key, an agent log, structured data, and HTML without active content, and the
view tab letters following the committed bar through a cancelled stage.

`cli-ui-modified-keys.tryscript.md` shows every chord left to the browser, and
`cli-ui-nav-collapse.tryscript.md` hiding the navigation pane with Backslash.

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
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "4 opens the closed drawer and the file type filter, and focuses its checked row",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "drawerBefore": false,
      "pressed": {
        "key": "4",
        "handled": true
      },
      "drawerAfter": true,
      "focus": {
        "menu": "filter-type-menu",
        "row": "Any type",
        "checked": "true",
        "open": "true"
      },
      "did": ["opened the types menu"]
    },
    {
      "step": "↓ moves to the next row, a pick or a rebuild keeps focus there, and Escape closes the menu onto its trigger",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "next": {
        "menu": "filter-type-menu",
        "row": ".md",
        "checked": "false",
        "open": "true"
      },
      "picked": {
        "menu": "filter-type-menu",
        "row": ".md",
        "checked": "false",
        "open": "true"
      },
      "rebuilt": {
        "menu": "filter-type-menu",
        "row": ".md",
        "checked": "false",
        "open": "true"
      },
      "escaped": "the types trigger",
      "did": ["chose .md in the types menu","closed the types menu"]
    },
    {
      "step": "each way a menu opens focuses its checked row, and each way it closes its trigger",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "byNumber": {
        "menu": "filter-recency-menu",
        "row": "Any age",
        "checked": "true",
        "open": "true"
      },
      "byNumberEscaped": "the recency trigger",
      "byArrow": {
        "menu": "filter-group-menu",
        "row": "No grouping",
        "checked": "true",
        "open": "true"
      },
      "byArrowEscaped": "the group trigger",
      "byClick": {
        "menu": "filter-group-menu",
        "row": "No grouping",
        "checked": "true",
        "open": "true"
      },
      "byClickClosed": "the group trigger",
      "did": ["opened the recency menu","closed the recency menu","opened the group menu","closed the group menu","opened the group menu","closed the group menu"]
    },
    {
      "step": "Help lists Group by's letters under Menus",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "menus": [
        ["N","No grouping","Choose No grouping in the Group by menu."],
        ["A","By age","Choose By age in the Group by menu."],
        ["T","By file type","Choose By file type in the Group by menu."]
      ]
    },
    {
      "step": "2 opens Group by and focuses its checked row, whose letters are live",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null],
        ["N","menu.group.n","No grouping row"],
        ["A","menu.group.a","By age row"],
        ["T","menu.group.t","By file type row"]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "focus": {
        "menu": "filter-group-menu",
        "row": "No grouping",
        "checked": "true",
        "open": "true"
      },
      "did": ["opened the group menu"]
    },
    {
      "step": "Shift held in the open menu badges its rows' letters",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null],
        ["N","menu.group.n","No grouping row"],
        ["A","menu.group.a","By age row"],
        ["T","menu.group.t","By file type row"]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [
        ["0","beside, in app-header"],
        ["1","beside, in app-header"],
        ["F","Files tab"],
        ["2","Group by"],
        ["N","No grouping row"],
        ["A","By age row"],
        ["T","By file type row"],
        ["3","Modified within"],
        ["4","File type"],
        ["O","Overview tab"],
        ["M","Treemap tab"],
        ["\\","beside, in preview-frame"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","/ Quick Search","0 Home","F Files","N No grouping","A By age","T By file type"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "A chooses By age and closes the menu",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
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
        "key": "a",
        "handled": true
      },
      "trigger": "By age",
      "focus": "the group trigger",
      "did": ["chose age in the group menu"]
    },
    {
      "step": "with the menu closed, T is Quick Search",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["↑","quick-file.previous",null],
        ["↓","quick-file.next",null],
        ["Enter","quick-file.activate",null],
        ["Esc","quick-file.close",null]
      ],
      "numbers": [],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "t",
        "handled": true
      },
      "focus": "combobox"
    },
    {
      "step": "2 focuses By age, the checked row, and T chooses By file type",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "focus": {
        "menu": "filter-group-menu",
        "row": "By age",
        "checked": "true",
        "open": "true"
      },
      "pressed": {
        "key": "t",
        "handled": true
      },
      "trigger": "By file type",
      "did": ["opened the group menu","chose type in the group menu"]
    },
    {
      "step": "with focus outside the open menu, T is Quick Search, which closes it",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["↑","quick-file.previous",null],
        ["↓","quick-file.next",null],
        ["Enter","quick-file.activate",null],
        ["Esc","quick-file.close",null]
      ],
      "numbers": [],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "t",
        "handled": true
      },
      "focus": "combobox",
      "trigger": "By file type",
      "did": ["opened the group menu","closed the group menu"]
    },
    {
      "step": "N chooses No grouping",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
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
        "key": "n",
        "handled": true
      },
      "trigger": "No grouping",
      "did": ["opened the group menu","chose the any-row in the group menu"]
    },
    {
      "step": "a Markdown file has Document and Source",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
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
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
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
      "cost": {
        "publications": ["batch(target)"],
        "targetReads": 0,
        "keycapsCreated": 0
      }
    },
    {
      "step": "copying is ancillary: the Copy path button has no key, and Y does nothing",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
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
        "key": "y",
        "handled": false
      },
      "ancillary": ["Copy path"]
    },
    {
      "step": "a folder below the root has Up",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "U opens the folder above",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
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
      "did": ["opened the folder \"\""]
    },
    {
      "step": "the root folder has no Up",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
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
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "did": ["selected the treemap tab"]
    },
    {
      "step": "0 goes home, through the folder's name's own path",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["A","view-tabs.a","Values tab"],
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
        "key": "0",
        "handled": true
      },
      "did": ["went home"]
    },
    {
      "step": "Shift-0, which types ) on a US keyboard, goes home too",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["A","view-tabs.a","Values tab"],
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
        "key": ")",
        "handled": true
      },
      "did": ["went home"]
    },
    {
      "step": "an agent log has Log, Charts, and Raw JSON",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["E","view-tabs.e","Session tab"],
        ["V","view-tabs.v","Log tab"],
        ["C","view-tabs.c","Charts tab"],
        ["S","view-tabs.s","Raw JSON tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "V follows the committed bar, and a cancelled stage changes nothing",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["A","view-tabs.a","Values tab"],
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
      "v": {
        "structured": "Tree",
        "agentLog": "Log",
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
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","controls","numbered","navigation","menus","quick-file","help"]
    }
  ],
  "shellKeys": ["0","1","2","3","4","5","6","7","8","9","f","h","j","k","p","t","u"],
  "shellCommands": ["0 shell.home: Home","f main-tabs.files: Open Files","h main-tabs.git: Open Commits","j tree.next: Next item","k tree.previous: Previous item","p main-tabs.pulls: Open Pulls","t quick-file.open: Quick Search","u header.parent: Parent folder"]
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
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
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
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "Shift held past the threshold reveals",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [
        ["0","beside, in app-header"],
        ["1","beside, in app-header"],
        ["F","Files tab"],
        ["2","Group by"],
        ["3","Modified within"],
        ["4","File type"],
        ["U","beside, in file-header view-header"],
        ["V","Document tab"],
        ["S","Source tab"],
        ["\\","beside, in preview-frame"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","0 Home","F Files","U Up"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "a navigation while revealed moves the badges in one pass",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["A","view-tabs.a","Values tab"],
        ["V","view-tabs.v","Tree tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [
        ["0","beside, in app-header"],
        ["1","beside, in app-header"],
        ["F","Files tab"],
        ["2","Group by"],
        ["3","Modified within"],
        ["4","File type"],
        ["U","beside, in file-header view-header"],
        ["A","Values tab"],
        ["V","Tree tab"],
        ["S","Source tab"],
        ["\\","beside, in preview-frame"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","0 Home","F Files","U Up"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "cost": {
        "publications": ["batch(registration,target)"],
        "targetReads": 9,
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
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
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
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "a capital typed within the threshold never reveals",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
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
      "numbers": [],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "Shift+wheel never reveals",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
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
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "Shift with the pointer travelling to a click never reveals",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
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
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "a resting hand within the slop still reveals",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [
        ["0","beside, in app-header"],
        ["1","beside, in app-header"],
        ["F","Files tab"],
        ["2","Group by"],
        ["3","Modified within"],
        ["4","File type"],
        ["U","beside, in file-header view-header"],
        ["V","Document tab"],
        ["S","Source tab"],
        ["\\","beside, in preview-frame"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","0 Home","F Files","U Up"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "a pointer press while revealed dismisses it",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
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
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "Shift during a press that moved focus never reveals",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "focusedRow": "docs"
    },
    {
      "step": "↑ on a tree row moves one row and keeps the reveal",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [
        ["0","beside, in app-header"],
        ["1","beside, in app-header"],
        ["F","Files tab"],
        ["2","Group by"],
        ["3","Modified within"],
        ["4","File type"],
        ["U","beside, in file-header view-header"],
        ["V","Document tab"],
        ["S","Source tab"],
        ["\\","beside, in preview-frame"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","0 Home","F Files","U Up"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "ArrowUp",
        "handled": true
      },
      "focusedRow": "README.md",
      "cost": {
        "publications": ["dispatch"],
        "targetReads": 8,
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
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [
        ["0","beside, in app-header"],
        ["1","beside, in app-header"],
        ["F","Files tab"],
        ["2","Group by"],
        ["3","Modified within"],
        ["4","File type"],
        ["U","beside, in file-header view-header"],
        ["V","Document tab"],
        ["S","Source tab"],
        ["\\","beside, in preview-frame"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","0 Home","F Files","U Up"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
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
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
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
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "a key without Shift ends a reveal whose keyup was lost",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "the page going hidden ends the reveal",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
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
      "numbers": [],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "focus": "combobox"
    },
    {
      "step": "with Help open only Help's keys are live",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["? or Esc","help.close",null]
      ],
      "numbers": [],
      "badges": [],
      "strip": {
        "surface": "reveal",
        "items": []
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "the keymap after a pageshow rebuild",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["V","view-tabs.v","Document tab"],
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
      "sameAsBefore": true
    }
  ],
  "shellKeys": ["0","1","2","3","4","5","6","7","8","9","f","h","j","k","p","t","u"],
  "shellCommands": ["0 shell.home: Home","f main-tabs.files: Open Files","h main-tabs.git: Open Commits","j tree.next: Next item","k tree.previous: Previous item","p main-tabs.pulls: Open Pulls","t quick-file.open: Quick Search","u header.parent: Parent folder"]
}
? 0
```

## The Main Tabs, a Commit, a Stack, and a Pin

`H` and `F` under a held Shift, a commit view’s Copy revision with no key, Commits
registered while the registry is down, Pulls drawn before Git discovery and the tab
order Files, Pulls, Commits, the Preview tab’s `V` with Control-P left to the stack, `P`
opening the Pulls tab, a pull request in and outside a stack, where Control-N and
Control-P walk it on a Mac, the session’s navigator and where alone they are bound, a
chord ends a reveal, and `N` alone and AltGr’s Control-Alt walk nothing, a mirror’s pin
with its branch switcher, Group by numbered 1 and its one filter 2, and Help’s one
positional row for the numbers.

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
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["H","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "H with Shift still held opens Commits, focuses its row, and keeps the reveal",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["H","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh"],
      "badges": [
        ["0","beside, in app-header"],
        ["1","beside, in app-header"],
        ["F","Files tab"],
        ["H","Commits tab"],
        ["O","Overview tab"],
        ["M","Treemap tab"],
        ["\\","beside, in preview-frame"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","0 Home","F Files","H Commits"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "h",
        "handled": true
      },
      "active": "git",
      "focus": "a1",
      "did": ["address /view/"]
    },
    {
      "step": "F during the reveal shows the filter bar, and Group by and its filters gain 2 to 4",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["H","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [
        ["0","beside, in app-header"],
        ["1","beside, in app-header"],
        ["F","Files tab"],
        ["H","Commits tab"],
        ["2","Group by"],
        ["3","Modified within"],
        ["4","File type"],
        ["O","Overview tab"],
        ["M","Treemap tab"],
        ["\\","beside, in preview-frame"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","0 Home","F Files","H Commits"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "f",
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
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["H","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null],
        ["↑ or K","tree.previous",null],
        ["↓ or J","tree.next",null],
        ["←","tree.parent-or-collapse",null],
        ["→","tree.child-or-expand",null],
        ["Home","tree.first",null],
        ["End","tree.last",null],
        ["Enter or Space","tree.activate",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"]
    },
    {
      "step": "J on a commit row ends the reveal, since the row handles it itself",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["H","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "did": ["address /view/","the commit row moved down from a1"]
    },
    {
      "step": "a commit view's Copy revision is ancillary and has no key",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["H","main-tabs.git","Commits tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "y",
        "handled": false
      },
      "ancillary": ["Copy revision"]
    },
    {
      "step": "Commits registered while the registry is down gets its tab, then its key",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["H","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "whileDown": {
        "threw": null,
        "tab": true,
        "container": true,
        "key": null
      },
      "key": "H",
      "pressed": {
        "key": "h",
        "handled": true
      },
      "active": "git",
      "did": ["address /view/"]
    },
    {
      "step": "Pulls drawn before Commits has P, and H does nothing until Commits comes",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["P","main-tabs.pulls","Pulls tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","pull-requests","pull-stack","quick-file","help"],
      "pressed": {
        "key": "h",
        "handled": false
      },
      "tabs": ["Files","Pulls"]
    },
    {
      "step": "a repository with a hosted origin shows Files, Pulls, and Commits",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["P","main-tabs.pulls","Pulls tab"],
        ["H","main-tabs.git","Commits tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","Modified within","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","pull-requests","pull-stack","quick-file","help"],
      "tabs": ["Files","Pulls","Commits"]
    },
    {
      "step": "the Preview tab is V, and Control-P outside a stack does nothing",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["P","main-tabs.pulls","Pulls tab"],
        ["H","main-tabs.git","Commits tab"],
        ["V","view-tabs.v","Preview tab"],
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
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","pull-requests","pull-stack","quick-file","help"],
      "pressed": {
        "key": "v",
        "handled": true
      },
      "controlP": false,
      "did": ["selected the preview tab"]
    },
    {
      "step": "P opens the Pulls tab from a file",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["P","main-tabs.pulls","Pulls tab"],
        ["H","main-tabs.git","Commits tab"],
        ["V","view-tabs.v","Preview tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","pull-requests","pull-stack","quick-file","help"],
      "pressed": {
        "key": "p",
        "handled": true
      },
      "active": "pulls",
      "did": ["address /pulls"]
    },
    {
      "step": "P again, once the list has rows, moves focus to the selected row",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["P","main-tabs.pulls","Pulls tab"],
        ["H","main-tabs.git","Commits tab"],
        ["V","view-tabs.v","Preview tab"],
        ["S","view-tabs.s","Source tab"],
        ["U","header.parent","Open parent folder /"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","pull-requests","pull-stack","quick-file","help"],
      "pressed": {
        "key": "p",
        "handled": true
      },
      "focus": "#7"
    },
    {
      "step": "a pull request outside a stack has no Control-N or Control-P",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["P","main-tabs.pulls","Pulls tab"],
        ["H","main-tabs.git","Commits tab"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","controls","numbered","navigation","menus","pull-requests","pull-stack","quick-file","help"],
      "focus": "#7",
      "pressed": {
        "key": "Control-n",
        "handled": false
      }
    },
    {
      "step": "a pull request in a stack lists Control-N or Control-P on the strip",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["P","main-tabs.pulls","Pulls tab"],
        ["H","main-tabs.git","Commits tab"],
        ["1–9","numbered",null],
        ["⌃N","pulls.stack.top",null],
        ["⌃P","pulls.stack.base",null]
      ],
      "numbers": ["Refresh"],
      "badges": [
        ["0","beside, in app-header"],
        ["1","beside, in app-header"],
        ["F","Files tab"],
        ["P","Pulls tab"],
        ["H","Commits tab"],
        ["\\","beside, in preview-frame"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","0 Home","F Files","P Pulls","H Commits","⌃N or ⌃P Stack"]
      },
      "help": ["anywhere","main-tabs","controls","numbered","navigation","menus","pull-requests","pull-stack","quick-file","help"]
    },
    {
      "step": "Control-N with Shift held walks the stack and ends the reveal",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["P","main-tabs.pulls","Pulls tab"],
        ["H","main-tabs.git","Commits tab"],
        ["1–9","numbered",null],
        ["⌃N","pulls.stack.top",null],
        ["⌃P","pulls.stack.base",null]
      ],
      "numbers": ["Refresh"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","controls","numbered","navigation","menus","pull-requests","pull-stack","quick-file","help"],
      "pressed": {
        "key": "Control-n",
        "handled": true
      },
      "did": ["moved toward the stack's top"]
    },
    {
      "step": "Control-P walks the stack toward its base",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["P","main-tabs.pulls","Pulls tab"],
        ["H","main-tabs.git","Commits tab"],
        ["1–9","numbered",null],
        ["⌃N","pulls.stack.top",null],
        ["⌃P","pulls.stack.base",null]
      ],
      "numbers": ["Refresh"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","controls","numbered","navigation","menus","pull-requests","pull-stack","quick-file","help"],
      "pressed": {
        "key": "Control-p",
        "handled": true
      },
      "did": ["moved toward its base"]
    },
    {
      "step": "N alone and Control-Alt-N walk nothing, and P alone is the Pulls tab",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["P","main-tabs.pulls","Pulls tab"],
        ["H","main-tabs.git","Commits tab"],
        ["1–9","numbered",null],
        ["⌃N","pulls.stack.top",null],
        ["⌃P","pulls.stack.base",null]
      ],
      "numbers": ["Refresh"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","controls","numbered","navigation","menus","pull-requests","pull-stack","quick-file","help"],
      "n": false,
      "altGr": false,
      "p": {
        "handled": true,
        "active": "pulls",
        "focus": "#7"
      }
    },
    {
      "step": "a mirror's pin has W, Group by is 2, and its one filter is 3",
      "reveal": "idle",
      "rootMarked": false,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["W","source.switch-ref","Branch: topic"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","File type"],
      "badges": [],
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "pressed": {
        "key": "w",
        "handled": true
      },
      "four": false,
      "did": ["opened the branch list and focused its filter"]
    },
    {
      "step": "Help lists the numbers once, as positional",
      "reveal": "revealed",
      "rootMarked": true,
      "keys": [
        ["?","help.open",null],
        ["T or /","quick-file.open",null],
        ["0","shell.home","squares"],
        ["\\","shell.nav-toggle","Hide navigation"],
        ["F","main-tabs.files","Files tab"],
        ["O","view-tabs.o","Overview tab"],
        ["M","view-tabs.m","Treemap tab"],
        ["W","source.switch-ref","Branch: topic"],
        ["1–9","numbered",null]
      ],
      "numbers": ["Refresh","Group by","File type"],
      "badges": [
        ["0","beside, in app-header"],
        ["1","beside, in app-header"],
        ["F","Files tab"],
        ["2","Group by"],
        ["3","File type"],
        ["W","Branch: topic"],
        ["O","Overview tab"],
        ["M","Treemap tab"],
        ["\\","beside, in preview-frame"]
      ],
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search","0 Home","F Files","W Branch"]
      },
      "help": ["anywhere","main-tabs","view-tabs","controls","numbered","navigation","menus","quick-file","help"],
      "helpDigits": [
        {
          "keys": "0",
          "range": false,
          "action": "Home"
        },
        {
          "keys": "1–9",
          "range": true,
          "action": "Numbered links and actions"
        }
      ],
      "menus": [
        ["N","No grouping","Choose No grouping in the Group by menu."],
        ["T","By file type","Choose By file type in the Group by menu."]
      ]
    }
  ],
  "shellKeys": ["0","1","2","3","4","5","6","7","8","9","control-n","control-p","f","h","j","k","p","t","u","w"],
  "shellCommands": ["0 shell.home: Home","control-n pulls.stack.top: Next in stack","control-p pulls.stack.base: Previous in stack","f main-tabs.files: Open Files","h main-tabs.git: Open Commits","j pulls.files.next: Next changed file","j pulls.next: Next pull request","j tree.next: Next item","k pulls.files.previous: Previous changed file","k pulls.previous: Previous pull request","k tree.previous: Previous item","p main-tabs.pulls: Open Pulls","t quick-file.open: Quick Search","u header.parent: Parent folder","w source.switch-ref: Branch or tag"]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
