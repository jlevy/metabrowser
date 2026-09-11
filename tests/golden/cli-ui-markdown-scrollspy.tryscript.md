---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Rendered Markdown TOC Scrollspy

This browserless session calls the exact production `mountRenderedMarkdown` path, which
runs the Markdown link enhancer over KPress’s authored same-document TOC links before it
initializes the installed KPress TOC module through the production observation fallback.
It pins the fragment-only link contract KPress consumes, delegated Metabrowser
navigation, and canonical embedded-document fragment links used by modified clicks, new
tabs, and Copy Link.
It also pins the active section across a long heading interval, one update per animation
frame, zero catalog reads for fragment-only links, expand-all state and accessible
labels, complete listener disposal, and preservation of a native observer when one
exists.

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
      "window": 0
    },
    "pendingFramesAfterDispose": 0,
    "tocBindingDisposed": true
  },
  "fallbackWasScoped": true,
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
  "nativeRuntimePreserved": true,
  "passiveScrollListener": true,
  "productionModules": {
    "kpressToc": true,
    "renderedMarkdownMount": true,
    "tocIntersectionFallback": true
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
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
