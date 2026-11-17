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
      "scrollTop": 0
    },
    {
      "active": "design",
      "label": "design section",
      "scrollTop": 750
    },
    {
      "active": "implementation-plan",
      "label": "implementation plan heading",
      "scrollTop": 4050
    },
    {
      "active": "implementation-plan",
      "label": "middle of long implementation plan",
      "scrollTop": 11000
    },
    {
      "active": "testing",
      "label": "testing section after scroll burst",
      "scrollTop": 14100
    },
    {
      "active": "design",
      "label": "design heading above the reading line",
      "scrollTop": 450
    },
    {
      "active": "overview",
      "label": "pane resized to half height",
      "scrollTop": 450
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
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
