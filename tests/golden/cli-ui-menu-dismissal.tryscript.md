---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: How Every Menu Closes

Every menu in the shell and its built-in plugins closes alike (docs/design-system.md,
“Every Menu Closes Alike”), through `metabrowser.menus.dismissible`, which
`static/filter-controls.js` puts on the SDK and `static/menus.js`, one of the shell’s
tools, carries out. This browserless session loads both whole on the key reveal’s
stand-in DOM, which keeps focus, event capture and bubbling, and the window’s blur.
A press is a browser’s: down, then focus for a button or a checkbox and none for
anything else, then the click.

`menu` is one menu as a plugin wires it.
A press or a tap outside it and its trigger closes it (`outside`), focus arriving
outside them does (`away`), and so does the window losing focus, to a frame whose
presses never reach the page or to another window (`away`). Escape closes it and gives
focus back to its trigger (`escape`), unless a surface above it took the key first or it
is held with a modifier.
A press inside it, and focus that goes nowhere, leave it open; a second press on its
trigger closes it as the trigger’s own click does.
Opening one menu closes another (`other`), and a press on another menu’s trigger closes
the first as any outside press does, then opens the second.
`listening` counts the listeners on the document and the window, held only while a menu
is open, and a menu disposed while open lets them go.

`filesBar` is the Files tab’s filter bar as `app.js` draws it, from the same renderers
and `bind`, its consumer rebuilding the bar on every change.
Group by, Modified within, and File type close on a press on the bar beside them, on the
drawer’s chevron, on Show ignored, on another dropdown’s trigger, and outside the bar; a
press in the bar closes the open dropdown once what it landed on has acted, so the
drawer opens, Show ignored turns off, and the other dropdown opens (`acted`). Escape
gives focus back to the dropdown’s trigger, and a menu elsewhere opening closes the open
dropdown, and the other way around.

`early` is a menu that opens before the shell’s tools arrive: it asks for them, and once
they land it closes as every menu does.

The session asserts that the document is listened to exactly while a menu is open.

```console
$ node tests/dom/menu-dismissal-session.js
{
  "menu": [
    {
      "step": "nothing open",
      "open": [],
      "closed": [],
      "focus": "the page",
      "listening": 0
    },
    {
      "step": "a press on A's trigger opens it",
      "open": [
        "A"
      ],
      "closed": [],
      "focus": "A first item",
      "listening": 5
    },
    {
      "step": "a press inside it leaves it open",
      "open": [
        "A"
      ],
      "closed": [],
      "focus": "A first item",
      "listening": 5
    },
    {
      "step": "a press on a button outside closes it",
      "open": [],
      "closed": [
        "A: outside"
      ],
      "focus": "a button outside",
      "listening": 0
    },
    {
      "step": "a press on text outside closes it",
      "open": [],
      "closed": [
        "A: outside"
      ],
      "focus": "the page",
      "listening": 0
    },
    {
      "step": "a second press on its trigger closes it",
      "open": [],
      "closed": [],
      "focus": "A trigger",
      "listening": 0
    },
    {
      "step": "Escape closes it and gives focus back to its trigger",
      "open": [],
      "closed": [
        "A: escape"
      ],
      "focus": "A trigger",
      "listening": 0,
      "prevented": true
    },
    {
      "step": "an Escape a surface above took first leaves it open",
      "open": [
        "A"
      ],
      "closed": [],
      "focus": "A first item",
      "listening": 5,
      "prevented": true
    },
    {
      "step": "Option-Escape is the browser's and leaves it open",
      "open": [
        "A"
      ],
      "closed": [],
      "focus": "A first item",
      "listening": 5,
      "prevented": false
    },
    {
      "step": "focus arriving outside closes it",
      "open": [],
      "closed": [
        "A: away"
      ],
      "focus": "a button outside",
      "listening": 0
    },
    {
      "step": "focus that goes nowhere leaves it to a press",
      "open": [
        "A"
      ],
      "closed": [],
      "focus": "the page",
      "listening": 5
    },
    {
      "step": "the window losing focus, to a frame or another window, closes it",
      "open": [],
      "closed": [
        "A: away"
      ],
      "focus": "the page",
      "listening": 0
    },
    {
      "step": "B opening by a key, with focus left in A, closes A",
      "open": [
        "B"
      ],
      "closed": [
        "A: other"
      ],
      "focus": "A first item",
      "listening": 5
    },
    {
      "step": "a press on B's trigger closes A and opens B",
      "open": [
        "B"
      ],
      "closed": [
        "A: outside"
      ],
      "focus": "B first item",
      "listening": 5
    },
    {
      "step": "a menu disposed open, as when its view goes, lets the document go",
      "open": [
        "B"
      ],
      "closed": [],
      "focus": "B first item",
      "listening": 0,
      "disposed": "B"
    }
  ],
  "filesBar": [
    {
      "step": "a press on Group by opens it",
      "open": "group",
      "acted": [],
      "focus": "group",
      "listening": 5
    },
    {
      "step": "a press on the bar beside it closes it",
      "open": "none",
      "acted": [],
      "focus": "the page",
      "listening": 0
    },
    {
      "step": "a press on the drawer's chevron closes Group by and opens the drawer",
      "open": "none",
      "acted": [
        "drawer on"
      ],
      "focus": "drawer",
      "listening": 0
    },
    {
      "step": "a press on Modified within, with File type open, opens Modified within",
      "open": "recency",
      "acted": [],
      "focus": "recency",
      "listening": 5
    },
    {
      "step": "a press on Show ignored closes Modified within and turns Show ignored off",
      "open": "none",
      "acted": [
        "showIgnored off"
      ],
      "focus": "showIgnored",
      "listening": 0
    },
    {
      "step": "a press outside the bar closes File type",
      "open": "none",
      "acted": [],
      "focus": "a tree row",
      "listening": 0
    },
    {
      "step": "a second press on Group by closes it",
      "open": "none",
      "acted": [],
      "focus": "group",
      "listening": 0
    },
    {
      "step": "Escape closes File type and gives focus back to its trigger",
      "open": "none",
      "acted": [],
      "focus": "types",
      "listening": 0
    },
    {
      "step": "another menu opening closes Group by",
      "open": "none",
      "otherMenu": "open",
      "acted": [],
      "focus": "group",
      "listening": 5
    },
    {
      "step": "Group by opening closes the other menu",
      "open": "group",
      "acted": [],
      "focus": "group",
      "listening": 5
    },
    {
      "step": "unbinding the bar with Group by drawn open lets the document go",
      "open": "group",
      "unbound": true,
      "acted": [],
      "focus": "group",
      "listening": 0
    }
  ],
  "early": [
    {
      "step": "a menu opens before the shell's tools: it asks for them",
      "asked": [
        "shell-tools"
      ],
      "listening": 0
    },
    {
      "step": "they land, and the open menu listens",
      "listening": 5
    },
    {
      "step": "a press outside closes it",
      "closed": [
        "outside"
      ],
      "listening": 0
    }
  ]
}
? 0
```
