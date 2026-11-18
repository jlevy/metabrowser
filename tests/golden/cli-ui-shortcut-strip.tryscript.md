---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Shortcut Strip Stays One Row

The strip at the foot of the navigation pane lists Shift first, as Reveal keys, ahead of
`?` for Help and `T` for Quick Search, and it is always one row (mb-k8am). Where its
items do not all fit, it drops them from the end, Quick Search first and then Help, and
always keeps Shift; holding Shift lists what it dropped on the revealed layer, and a
wider pane brings them back.
Text that grows, as another face or font set draws it, is measured again.

This browserless session runs the production registry, Help and its strip, the Shift
reveal, and Quick Search on the key reveal’s stand-in DOM, which lays nothing out: the
session gives the strip its box, the pane’s width less the pane’s 1px border, with the
stylesheet’s padding and gap, and gives its items the widths Chrome 152 drew them at in
the default font set (`STRIP_WIDTHS` in `tests/dom/shortcut-strip-session.js`), then
delivers each size change as a browser’s ResizeObserver would.
`panes` is what the strip shows at each pane width.
`tests/test_shortcut_strip_chrome.py` holds every pane width from the narrowest to the
default, in both font sets, to the same rule in Chrome itself.

```console
$ node tests/dom/shortcut-strip-session.js
{
  "steps": [
    {
      "step": "before a layout, the strip lists Shift, Help, and Quick Search",
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys","? Help","T Quick Search"]
      }
    },
    {
      "step": "a narrowing pane drops Quick Search, then Help, and keeps Shift",
      "panes": [
        [300,"Shift Reveal keys","? Help","T Quick Search"],
        [273,"Shift Reveal keys","? Help","T Quick Search"],
        [272,"Shift Reveal keys","? Help"],
        [200,"Shift Reveal keys","? Help"],
        [181,"Shift Reveal keys","? Help"],
        [180,"Shift Reveal keys"]
      ]
    },
    {
      "step": "Shift held in the narrowest pane lists what the strip dropped",
      "reveal": "revealed",
      "strip": {
        "surface": "reveal",
        "items": ["? Help","T or / Quick Search"]
      }
    },
    {
      "step": "Shift released, the narrowest pane shows Shift alone",
      "reveal": "idle",
      "strip": {
        "surface": "nav",
        "items": ["Shift Reveal keys"]
      }
    },
    {
      "step": "a widening pane brings Help, then Quick Search, back",
      "panes": [
        [180,"Shift Reveal keys"],
        [181,"Shift Reveal keys","? Help"],
        [272,"Shift Reveal keys","? Help"],
        [273,"Shift Reveal keys","? Help","T Quick Search"],
        [300,"Shift Reveal keys","? Help","T Quick Search"]
      ]
    },
    {
      "step": "wider text is measured again: the default pane drops Quick Search, a pixel more keeps it",
      "panes": [
        [300,"Shift Reveal keys","? Help"],
        [301,"Shift Reveal keys","? Help","T Quick Search"]
      ]
    },
    {
      "step": "disposed, Help empties the strip and stops observing it",
      "strip": {
        "surface": "nav",
        "items": []
      },
      "observing": 0
    }
  ]
}
? 0
```
