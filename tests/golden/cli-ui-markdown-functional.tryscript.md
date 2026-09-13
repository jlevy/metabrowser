---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Markdown Functional Semantics

This browserless session executes the production wiki resolver, root-scoped catalog
reconciliation coordinator, published-route adapters, preprocessing Worker client, and
the real rendered-link to wiki-enhancer to nested-transclusion chain.
It pins exact, incomplete, ambiguous, overflow, revision, slice, disposal,
percent-identity, and shared root-budget behavior without requiring a browser.

```console
$ node tests/dom/markdown-functional-session.js
{
  "catalogReconciliation": {
    "firstSliceCommits": 31,
    "poisonReports": 1,
    "queuedAfterFirstSlice": 1,
    "revisionStates": [
      "pending",
      "internal"
    ],
    "settledCommits": 40
  },
  "publishedRoutes": {
    "complete": {
      "candidates": [
        "_pages/guide.md",
        "docs/guide.md"
      ],
      "reason": "ambiguous-published-route",
      "status": "ambiguous"
    },
    "incomplete": {
      "reason": "catalog-incomplete",
      "status": "pending"
    },
    "percent": {
      "adapter": "mkdocs",
      "path": "docs/100%252F.md",
      "status": "internal"
    }
  },
  "standardLinks": {
    "externalHref": "https://example.com/out",
    "relativeHref": "/view/relative.md",
    "resourceSrc": "/raw?path=image.png",
    "unsafeStatus": "unsafe"
  },
  "transclusion": {
    "enhancedStandardLinks": 4091,
    "fetchedDocuments": 2,
    "readyDocuments": 2,
    "starvedWikiRemainsInert": true,
    "tocDisposals": 3
  },
  "wikiResolution": {
    "ambiguous": {
      "candidateCount": 25,
      "candidates": [
        "00/Leaf.md",
        "01/Leaf.md",
        "02/Leaf.md",
        "03/Leaf.md",
        "04/Leaf.md",
        "05/Leaf.md",
        "06/Leaf.md",
        "07/Leaf.md",
        "08/Leaf.md",
        "09/Leaf.md",
        "10/Leaf.md",
        "11/Leaf.md",
        "12/Leaf.md",
        "13/Leaf.md",
        "14/Leaf.md",
        "15/Leaf.md",
        "16/Leaf.md",
        "17/Leaf.md",
        "18/Leaf.md",
        "19/Leaf.md"
      ],
      "status": "ambiguous"
    },
    "exact": {
      "status": "internal",
      "path": "docs/Exact.md"
    },
    "overflow": {
      "status": "unsupported",
      "reason": "too-many-candidates"
    },
    "pending": {
      "status": "pending",
      "reason": "catalog-incomplete"
    }
  }
}
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
