---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Markdown Functional Semantics

This browserless session executes the production wiki parser and resolver, root-scoped
catalog reconciliation coordinator, published-route adapters, preprocessing Worker
client, and the real rendered-link to wiki-enhancer to nested-transclusion chain.
It pins exact, incomplete, truncated-catalog, ambiguous, overflow, revision, slice,
disposal, percent-identity, shared root-budget, task-list bracket-pairing, and page-wide
Worker sharing and recovery behavior without requiring a browser.

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
    "settledCommits": 40,
    "truncated": {
      "pinned": true,
      "rerunCallbacks": 0,
      "revisionStates": [
        "pending:catalog-incomplete",
        "unsupported:catalog-truncated"
      ]
    }
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
    },
    "truncated": {
      "reason": "catalog-truncated",
      "status": "unsupported"
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
    },
    "truncated": {
      "status": "unsupported",
      "reason": "catalog-truncated"
    }
  },
  "wikiPreprocessing": {
    "taskList": {
      "source": [
        "- [ ] Review <span class=\"metabrowser-wiki-link\" data-mb-wiki-target=\"Meeting Notes\" data-mb-wiki-action=\"navigate\">Meeting Notes</span> per [spec](https://example.com/spec)",
        "  - [x] Follow up in <span class=\"metabrowser-wiki-link\" data-mb-wiki-target=\"Notes#Actions\" data-mb-wiki-action=\"navigate\">actions</span> and [the [[Hidden]] log](log.md)",
        ""
      ],
      "targetCount": 2
    }
  },
  "workerSharing": {
    "aliveAfterOneRelease": true,
    "concurrentWorkers": 1,
    "fatalError": "session worker failed",
    "recovered": "after crash",
    "terminatedAfterLastRelease": true,
    "workersAfterRecovery": 2
  }
}
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
