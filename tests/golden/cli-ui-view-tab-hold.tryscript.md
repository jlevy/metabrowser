---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A View Tab Chosen While Its File Holds Its First Paint

The shell stages a file out of sight with its tab bar and holds the first paint until
the view in front has its data.
A tab chosen meanwhile wins: the commit brings it to the front, mounted once, and the
first view stays mounted to go back to.
The session runs the compositor’s tab functions (`bindTabs`, `selectTab`,
`setActiveView` and `stagedFile` in `view-composition.js`) and, verbatim from `app.js`,
the `renderFile` and `showPreviewTab` that order them, over the production view state
and pane lifecycle.

Each state reads `<path> in <view>` when the bar’s marked tab, its selected tab, the
content shown, the content marked active and the host’s view all name that one view;
where they differ, each is listed.
`mounts` counts each view’s renders.

- `noChoice`: the first view comes to the front and the other is not mounted.
- `clickDuringHold`: a click on the staged bar’s Treemap tab.
- `namedDuringHold`: the view asked for by name, as a second navigation to the file’s
  address asks.
- `namedBeforeTheStage`: asked for while the file’s envelope is still on its way, so the
  file opens in that view and its first view is not mounted at all.
- `namedForAnotherFile`: a view named for a file the pane is not loading is kept for no
  later render.
- `choiceWhileStagedAgain`: the file shown is staged again in the tab in front, as Load
  more’s render is, and the reader picks the other tab on the bar they see.
- `choiceWhileAnotherFileIsStaged`: a tab picked on the file shown while another file is
  staged is the shown file’s alone, and the other arrives whole in its own first view.
- `rereadMountedTreemap`: the shown Treemap stays mounted while Refresh reads new data
  and paints the answer in the same view.
  A lazy tab mounts with the updated context.
- `rereadWithIncompatibleViews`: changes to the view descriptors or a mounted view that
  cannot refresh in place use a staged replacement.

```console
$ node tests/dom/view-tab-hold-session.js
{
  "noChoice": {
    "held": {
      "staged": "src in overview",
      "pane": null,
      "mounts": "overview 1"
    },
    "after": {
      "committed": true,
      "staged": null,
      "pane": "src in overview",
      "mounts": "overview 1"
    }
  },
  "clickDuringHold": {
    "held": {
      "staged": "src in treemap",
      "pane": null,
      "mounts": "overview 1, treemap 1"
    },
    "after": {
      "committed": true,
      "staged": null,
      "pane": "src in treemap",
      "mounts": "overview 1, treemap 1"
    },
    "backToOverview": {
      "staged": null,
      "pane": "src in overview",
      "mounts": "overview 1, treemap 1"
    }
  },
  "namedDuringHold": {
    "held": {
      "staged": "src in treemap",
      "pane": null,
      "mounts": "overview 1, treemap 1"
    },
    "after": {
      "committed": true,
      "staged": null,
      "pane": "src in treemap",
      "mounts": "overview 1, treemap 1"
    }
  },
  "namedBeforeTheStage": {
    "before": {
      "staged": null,
      "pane": null,
      "mounts": ""
    },
    "after": {
      "committed": true,
      "staged": null,
      "pane": "src in treemap",
      "mounts": "treemap 1"
    }
  },
  "namedForAnotherFile": {
    "committed": true,
    "staged": null,
    "pane": "src in overview",
    "mounts": "overview 1"
  },
  "choiceWhileStagedAgain": {
    "shown": {
      "staged": null,
      "pane": "src in overview",
      "mounts": "overview 1"
    },
    "held": {
      "staged": "src in treemap",
      "pane": "src in treemap",
      "mounts": "overview 2, treemap 2"
    },
    "after": {
      "committed": true,
      "staged": null,
      "pane": "src in treemap",
      "mounts": "overview 2, treemap 2"
    }
  },
  "choiceWhileAnotherFileIsStaged": {
    "held": {
      "staged": "docs in overview",
      "pane": "src in treemap",
      "mounts": "overview 2, treemap 1"
    },
    "after": {
      "committed": true,
      "staged": null,
      "pane": "docs in overview",
      "mounts": "overview 2, treemap 1"
    }
  },
  "rereadMountedTreemap": {
    "held": {
      "staged": null,
      "pane": "src in treemap",
      "mounts": "treemap 1"
    },
    "oldContent": "treemap of src",
    "newContent": "updated map",
    "after": {
      "staged": null,
      "pane": "src in treemap",
      "mounts": "treemap 1"
    },
    "lazyContent": "updated map"
  },
  "rereadWithIncompatibleViews": {
    "changedDescriptor": {
      "label": "Folder map",
      "content": "fresh folder",
      "after": {
        "staged": null,
        "pane": "src in overview",
        "mounts": "treemap 2, overview 1"
      }
    },
    "unsupportedHidden": {
      "label": "Treemap",
      "content": "fresh folder",
      "after": {
        "staged": null,
        "pane": "src in overview",
        "mounts": "treemap 2, overview 2"
      }
    }
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
