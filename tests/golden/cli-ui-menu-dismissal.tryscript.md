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
WebKit’s press focuses no button: it gives focus to the nearest ancestor a press can
focus, or takes it off the focused element where there is none.

`menu` is one menu as a plugin wires it.
A press or a tap outside it and its trigger closes it (`outside`), focus arriving
outside them does (`away`), and so does the window losing focus, to a frame whose
presses never reach the page or to another window (`away`). Escape closes it and gives
focus back to its trigger (`escape`), unless a surface above it took the key first or it
is held with a modifier.
A press inside it, a drag from a field in it let go outside, whose click lands on an
ancestor of both, and focus that goes nowhere leave it open; a second press on its
trigger closes it as the trigger’s own click does.
Opening one menu closes another (`other`), and a press on another menu’s trigger closes
the first as any outside press does, then opens the second.
A menu opened with focus outside it and its trigger takes focus to its trigger: `G`,
which does not focus its own rows, opened by WebKit’s press with focus on a tree row,
stays open when the tree is rebuilt, since the tree gives focus back only to a row that
had it. Focus a press moves is that press’s own: `P` is in a pane a press can focus, as
every view’s menu is in the preview pane, and WebKit’s press on its item gives the pane
focus and leaves `P` open, so its click reaches the item (`picked`), and its second
press on the trigger closes it.
A press let go with no click keeps nothing: Tab then closes the menu as focus leaves.
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
A consumer that binds the bar again on every paint, as the Agents list does while its
summary loads, binds a dropdown already drawn open, which keeps closing as before.
A container bound around the bar leaves the bar’s open dropdown to the bar, as a diff’s
Markdown layer, which binds the whole diff, leaves the File type menu in its toolbar
open.

`early` is menus that open before the shell’s tools arrive: each asks for them.
Once they land, the one still open closes as every menu does, while one closed or whose
view went meanwhile stays out of it, as does a filter bar’s binding replaced meanwhile:
neither closes the menu that is open.

The session asserts that the document is listened to exactly while a menu is open and
the shell’s tools have landed, that WebKit’s press in `P` leaves it open and reaches its
item, and that the container bound around the bar leaves File type open.

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
      "step": "a drag from a field in it, let go outside, leaves it open",
      "open": [
        "A"
      ],
      "closed": [],
      "focus": "A field",
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
      "focus": "B trigger",
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
      "step": "G opened by WebKit's press, which takes focus off a tree row, takes focus to G",
      "open": [
        "G"
      ],
      "closed": [],
      "focus": "G trigger",
      "listening": 5
    },
    {
      "step": "a tree rebuild that keeps its focused row's focus leaves G open",
      "open": [
        "G"
      ],
      "closed": [],
      "focus": "G trigger",
      "listening": 5
    },
    {
      "step": "WebKit's press on an item of P, in a pane it gives focus to, leaves P open",
      "open": [
        "P"
      ],
      "closed": [],
      "focus": "the pane",
      "listening": 5,
      "picked": [
        "P first item"
      ]
    },
    {
      "step": "and its second press on P's trigger closes P",
      "open": [],
      "closed": [],
      "focus": "the pane",
      "listening": 0
    },
    {
      "step": "its press on an item let go with no click leaves P open",
      "open": [
        "P"
      ],
      "closed": [],
      "focus": "the pane",
      "listening": 5
    },
    {
      "step": "then Tab, taking focus outside, closes P",
      "open": [],
      "closed": [
        "P: away"
      ],
      "focus": "a button outside",
      "listening": 0
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
      "focus": "another menu's trigger",
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
      "step": "the bar bound again with Group by drawn open keeps it open and listening",
      "open": "group",
      "acted": [],
      "focus": "group",
      "listening": 5
    },
    {
      "step": "then a press outside the bar closes it",
      "open": "none",
      "acted": [],
      "focus": "a tree row",
      "listening": 0
    },
    {
      "step": "and, bound again twice, Escape closes it and gives focus back to its trigger",
      "open": "none",
      "acted": [],
      "focus": "group",
      "listening": 0
    },
    {
      "step": "a container bound around the bar with File type open leaves it open",
      "open": "types",
      "acted": [],
      "focus": "types",
      "listening": 5
    },
    {
      "step": "and a press outside both closes it",
      "open": "none",
      "acted": [],
      "focus": "a tree row",
      "listening": 0
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
      "step": "A opens before the shell's tools: it asks for them",
      "asked": [
        "shell-tools"
      ],
      "loaded": false,
      "open": [
        "A"
      ],
      "closed": [],
      "listening": 0
    },
    {
      "step": "B opens and closes before them",
      "loaded": false,
      "open": [
        "A"
      ],
      "closed": [],
      "listening": 0
    },
    {
      "step": "C opens and its view goes before them",
      "loaded": false,
      "open": [
        "A"
      ],
      "closed": [],
      "listening": 0
    },
    {
      "step": "they land: A listens, and B and C, closed or gone meanwhile, stay out of it",
      "loaded": true,
      "open": [
        "A"
      ],
      "closed": [],
      "listening": 5
    },
    {
      "step": "a press outside closes A",
      "loaded": true,
      "open": [],
      "closed": [
        "A: outside"
      ],
      "listening": 0
    },
    {
      "step": "a bar drawn with Group by open, bound and bound again before the shell's tools",
      "asked": [
        "shell-tools",
        "shell-tools"
      ],
      "loaded": false,
      "open": "group",
      "listening": 0
    },
    {
      "step": "they land: only its last binding listens, and Group by stays open",
      "loaded": true,
      "open": "group",
      "listening": 5
    },
    {
      "step": "a press outside the bar closes Group by",
      "loaded": true,
      "open": "none",
      "listening": 0
    }
  ]
}
? 0
```
