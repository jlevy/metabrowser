---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Rendered Markdown TOC Scrollspy

This browserless session calls the exact production `mountRenderedMarkdown` path, which
runs the Markdown link enhancer over KPress’s authored same-document TOC links before it
initializes the installed KPress TOC module.
The runtime has no `IntersectionObserver`, so KPress’s own scroll-listener fallback
drives the active section.
The installed KPress viewport module runs too: it finds the pane marked
`[data-kpress-viewport]`, registers the pane’s scroll listeners as passive, and observes
the pane for resizes, so a resize with no scroll moves the active section.
It pins the fragment-only link contract KPress consumes, delegated Metabrowser
navigation, and canonical embedded-document fragment links used by modified clicks, new
tabs, and Copy Link.
It also pins the active section across a long heading interval and a pane resize, one
update per animation frame, zero catalog reads for fragment-only links, expand-all state
and accessible labels, and complete listener and resize-observer disposal.

KPress’s toc.js runs with the narrow toggle’s policy the mount supplies
(`builtin_plugins/markdown/toc-toggle.js`), whose threshold is recorded beside KPress’s
own. In an opened file the toggle shows past the threshold, as KPress has it.
The `overview` block mounts a folder Overview’s README through the production README
panel, its document 1,000px down the pane: the toggle stays hidden past the threshold
until the reader reaches the README’s beginning, and hides again above it; the entries
keep fragment-only links, a click opens the heading on the folder’s page, and that
page’s fragment scrolls the README’s heading into view.
The folder’s address already names a README heading when the Overview mounts, as a deep
link does, so the mount’s first delivery of that fragment scrolls it into view
(`deepLinked`), although the README’s own path is not the page’s.

```console
$ node tests/dom/markdown-toc-scrollspy-session.js
{
  "coalescedFrames": 1,
  "dispose": {
    "listenersAfterDispose": {
      "container": 0,
      "document": 0,
      "toc": 0,
      "tocExpandAll": 0,
      "tocLinks": 0,
      "viewport": 0,
      "viewportResizeObservers": 0,
      "window": 0
    },
    "pendingFramesAfterDispose": 0,
    "tocBindingDisposed": true
  },
  "links": {
    "authoredHref": "#implementation-plan",
    "delegatedClickPrevented": true,
    "delegatedTarget": {
      "path": "docs/project/specs/active/plan.md",
      "fragment": "implementation-plan"
    },
    "embeddedDelegatedTarget": {
      "path": "docs/embedded.md",
      "fragment": "details"
    },
    "embeddedHref": "/view/docs/embedded.md#details",
    "embeddedModifierClickPrevented": false,
    "embeddedNewTabClickPrevented": false,
    "embeddedTargetBlankHref": "/view/docs/embedded.md#details",
    "enhancedHref": "#implementation-plan"
  },
  "maxHeadingGeometryReadsPerUpdate": 6,
  "overview": {
    "click": {
      "defaultPrevented": true,
      "opened": [
        {
          "path": "",
          "fragment": "direction"
        }
      ]
    },
    "fragment": {
      "deepLinked": [
        "quick-start"
      ],
      "scrolledTo": [
        "quick-start",
        "direction"
      ],
      "pendingFrames": 0
    },
    "hrefs": [
      "#why",
      "#quick-start",
      "#direction"
    ],
    "listenersAfterDispose": {
      "body": 0,
      "document": 0,
      "pane": 0,
      "toc": 0,
      "toggle": 0,
      "window": 0
    },
    "mountOptions": {
      "pagePath": ""
    },
    "readmeTop": 1000,
    "steps": [
      {
        "active": "why",
        "label": "top of the Overview",
        "scrollTop": 0,
        "toggleShown": false
      },
      {
        "active": "why",
        "label": "past the threshold, in the File Overview",
        "scrollTop": 500,
        "toggleShown": false
      },
      {
        "active": "why",
        "label": "the README just below the pane's top",
        "scrollTop": 980,
        "toggleShown": false
      },
      {
        "active": "why",
        "label": "the README's beginning reached",
        "scrollTop": 1005,
        "toggleShown": true
      },
      {
        "active": "quick-start",
        "label": "reading Quick Start",
        "scrollTop": 1650,
        "toggleShown": true
      },
      {
        "active": "quick-start",
        "label": "back up in the File Overview",
        "scrollTop": 500,
        "toggleShown": false
      }
    ]
  },
  "paneResizeObservers": 1,
  "passiveScrollListener": true,
  "productionModules": {
    "kpressToc": true,
    "kpressViewport": true,
    "renderedMarkdownMount": true
  },
  "productionOrder": {
    "tocMountedWithoutCatalogSnapshot": true,
    "catalogSnapshotsAfterFirstFlush": 0
  },
  "steps": [
    {
      "active": "overview",
      "label": "top",
      "scrollTop": 0,
      "toggleShown": false
    },
    {
      "active": "design",
      "label": "design section",
      "scrollTop": 750,
      "toggleShown": true
    },
    {
      "active": "implementation-plan",
      "label": "implementation plan heading",
      "scrollTop": 4050,
      "toggleShown": true
    },
    {
      "active": "implementation-plan",
      "label": "middle of long implementation plan",
      "scrollTop": 11000,
      "toggleShown": true
    },
    {
      "active": "testing",
      "label": "testing section after scroll burst",
      "scrollTop": 14100,
      "toggleShown": true
    },
    {
      "active": "design",
      "label": "design heading above the reading line",
      "scrollTop": 450,
      "toggleShown": true
    },
    {
      "active": "overview",
      "label": "pane resized to half height",
      "scrollTop": 450,
      "toggleShown": true
    },
    {
      "active": "overview",
      "label": "short of the toggle threshold",
      "scrollTop": 60,
      "toggleShown": false
    }
  ],
  "tocExpansion": {
    "beforeExpand": {
      "collapsedRows": 65,
      "expanded": "false",
      "label": "Expand TOC"
    },
    "afterExpand": {
      "collapsedRows": 0,
      "expanded": "true",
      "label": "Collapse TOC"
    },
    "afterCollapse": {
      "collapsedRows": 65,
      "expanded": "false",
      "label": "Expand TOC"
    },
    "afterDispose": {
      "collapsedRows": 0,
      "expanded": "false",
      "label": "Expand TOC"
    }
  },
  "toggleThreshold": {
    "kpress": 100,
    "metabrowser": 100
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
