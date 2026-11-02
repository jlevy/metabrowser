---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Which Layout a Diff Draws at Its Width

A diff draws the reader’s remembered layout, **Split** unless they chose **Unified**,
except that **Split** where it does not fit draws **Unified**: below its width its right
column is behind a sideways scroll, and an added line reads as a blank gap.
The width is the stylesheet’s 44 ems plus a file’s border, measured in Chrome and
recorded beside `SPLIT_MIN_WIDTH_EM`. The remembered choice is not written when this
happens, so **Split** returns when there is room, a little past the limit because
drawing the other layout can bring or take away the pane’s scrollbar.
The layout control shows what is drawn, and **Split** carries a tip saying why it is not
selected.
Choosing **Split** there draws it, with its sideways scroll, until the pane has
room and loses it again.
A pane that opens narrow draws **Unified** from its first draw and builds no Split row.

This browserless session loads the production `builtin_plugins/diff/diff-view.js` and
mounts a document of the conformance corpus into a small element tree.
The width a browser would report and the diff’s font size are given.
It asserts, and so prints nothing for, that a wide pane builds what a mount with no
observer does, node for node, that a report of the same width draws nothing, and that
disposing lets the observer go and drops a fit still waiting.

```console
$ node tests/dom/diff-layout-fit-session.js
{
  "steps": [
    {
      "step": "a wide pane draws Split, the default",
      "draws": "split",
      "splitRows": 3,
      "unifiedRows": 0,
      "builtSplit": true,
      "control": "split",
      "tips": [],
      "preference": []
    },
    {
      "step": "its first report changes nothing",
      "draws": "split",
      "splitRows": 3,
      "unifiedRows": 0,
      "builtSplit": true,
      "control": "split",
      "tips": [],
      "preference": []
    },
    {
      "step": "618 px is what Split needs: it still fits",
      "draws": "split",
      "splitRows": 3,
      "unifiedRows": 0,
      "builtSplit": true,
      "control": "split",
      "tips": [],
      "preference": []
    },
    {
      "step": "a pixel short: Unified, and the choice is not written",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": true,
      "control": "unified",
      "tips": [
        "Split: Too narrow for Split, so this shows Unified. Choose Split to scroll sideways."
      ],
      "preference": []
    },
    {
      "step": "room again, but within what a scrollbar could take back: still Unified",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": true,
      "control": "unified",
      "tips": [
        "Split: Too narrow for Split, so this shows Unified. Choose Split to scroll sideways."
      ],
      "preference": []
    },
    {
      "step": "still a pixel short of coming back",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": true,
      "control": "unified",
      "tips": [
        "Split: Too narrow for Split, so this shows Unified. Choose Split to scroll sideways."
      ],
      "preference": []
    },
    {
      "step": "Split, the reader's choice, returns",
      "draws": "split",
      "splitRows": 3,
      "unifiedRows": 0,
      "builtSplit": true,
      "control": "split",
      "tips": [],
      "preference": []
    },
    {
      "step": "two reports in one task: the last decides, and nothing is drawn for the first",
      "draws": "split",
      "splitRows": 3,
      "unifiedRows": 0,
      "builtSplit": true,
      "control": "split",
      "tips": [],
      "preference": []
    },
    {
      "step": "a hidden pane has no width: nothing changes",
      "draws": "split",
      "splitRows": 3,
      "unifiedRows": 0,
      "builtSplit": true,
      "control": "split",
      "tips": [],
      "preference": []
    },
    {
      "step": "opened narrow: Unified from the first draw, with no Split to throw away",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": false,
      "control": "unified",
      "tips": [
        "Split: Too narrow for Split, so this shows Unified. Choose Split to scroll sideways."
      ],
      "preference": []
    },
    {
      "step": "its first report changes nothing",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": false,
      "control": "unified",
      "tips": [
        "Split: Too narrow for Split, so this shows Unified. Choose Split to scroll sideways."
      ],
      "preference": []
    },
    {
      "step": "choosing what is drawn changes nothing, so Split stays the choice",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": false,
      "control": "unified",
      "tips": [
        "Split: Too narrow for Split, so this shows Unified. Choose Split to scroll sideways."
      ],
      "preference": []
    },
    {
      "step": "choosing Split where it does not fit gets it, with its sideways scroll",
      "draws": "split",
      "splitRows": 3,
      "unifiedRows": 0,
      "builtSplit": true,
      "control": "split",
      "tips": [],
      "preference": [
        "diff.layout=split"
      ]
    },
    {
      "step": "narrower or wider, it stays while the pane stays narrow",
      "draws": "split",
      "splitRows": 3,
      "unifiedRows": 0,
      "builtSplit": true,
      "control": "split",
      "tips": [],
      "preference": [
        "diff.layout=split"
      ]
    },
    {
      "step": "the pane has room",
      "draws": "split",
      "splitRows": 3,
      "unifiedRows": 0,
      "builtSplit": true,
      "control": "split",
      "tips": [],
      "preference": [
        "diff.layout=split"
      ]
    },
    {
      "step": "narrow again: the fallback is back",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": true,
      "control": "unified",
      "tips": [
        "Split: Too narrow for Split, so this shows Unified. Choose Split to scroll sideways."
      ],
      "preference": [
        "diff.layout=split"
      ]
    },
    {
      "step": "choosing Unified is a choice, and is written",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": true,
      "control": "unified",
      "tips": [],
      "preference": [
        "diff.layout=split",
        "diff.layout=split",
        "diff.layout=unified"
      ]
    },
    {
      "step": "with room, Unified stays",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": true,
      "control": "unified",
      "tips": [],
      "preference": [
        "diff.layout=split",
        "diff.layout=split",
        "diff.layout=unified"
      ]
    },
    {
      "step": "a reader who chose Unified, wide",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": false,
      "control": "unified",
      "tips": [],
      "preference": []
    },
    {
      "step": "narrow: nothing to do, and no tip",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": false,
      "control": "unified",
      "tips": [],
      "preference": []
    },
    {
      "step": "wide again: nothing done",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": false,
      "control": "unified",
      "tips": [],
      "preference": []
    },
    {
      "step": "a container not laid out yet: Split",
      "draws": "split",
      "splitRows": 3,
      "unifiedRows": 0,
      "builtSplit": true,
      "control": "split",
      "tips": [],
      "preference": []
    },
    {
      "step": "its first report is narrow: Unified",
      "draws": "unified",
      "splitRows": 0,
      "unifiedRows": 4,
      "builtSplit": true,
      "control": "unified",
      "tips": [
        "Split: Too narrow for Split, so this shows Unified. Choose Split to scroll sideways."
      ],
      "preference": []
    }
  ],
  "limit": [
    "617 px, had room: too narrow",
    "618 px, had room: fits",
    "617 px, was narrow: too narrow",
    "637 px, was narrow: too narrow",
    "638 px, was narrow: fits",
    "0 px, was narrow: too narrow",
    "0 px, had room: fits"
  ],
  "byTextSize": [
    "12 px text: Split fits from 530 px",
    "14 px text: Split fits from 618 px",
    "16 px text: Split fits from 706 px",
    "20 px text: Split fits from 882 px"
  ],
  "drawn": [
    "split: split",
    "split, narrow: unified",
    "split, narrow, insisted: split",
    "unified, narrow: unified"
  ]
}
? 0
```
