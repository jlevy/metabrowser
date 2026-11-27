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
It pins exact, incomplete, truncated-catalog, truncated-to-complete, ambiguous,
overflow, revision, slice, disposal, percent-identity, shared root-budget, task-list
bracket-pairing, heading-anchor placement, and page-wide Worker sharing, primary-first
dispatch, and recovery behavior without requiring a browser.

`pdfEmbeds` is a document’s PDFs through the same chain and the pdf plugin’s production
card. A link or wiki link to a PDF opens its view.
An embed, whether `![](…)`, `<img>`, an `<object>`, or `![[…]]`, is a slot holding a
link to the view until the plugin loads, then the card with one View link; it is never a
viewer and never `/raw`. A PDF named without `.pdf` stays an image of its `/raw`
address. The block also pins clicks, the plugin loading only for a document with a PDF,
print making a card’s image eager, disposal, a document replaced before the plugin
answers, and a page without the plugin.
Each link the document opens here, the link to the PDF by its path, the wiki link, and
each card’s View, has its link card (`linkCards`), the tooltip that says what it opens
(`static/link-previews.js`), registered through the SDK (`metabrowser.previewLink`), a
recording stand-in here, with the rendered root, on a plain folder’s page with no GitHub
identity and so no resolver, and the document’s disposal puts them away.

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
      "commitsAfterTruncatedChange": 0,
      "listensWhileTruncated": true,
      "pinnedAfterComplete": true,
      "revisionStates": [
        "pending:catalog-incomplete",
        "unsupported:catalog-truncated",
        "internal:notes/Later.md"
      ]
    }
  },
  "pdfEmbeds": {
    "pluginLoadsWithoutAPdf": 0,
    "beforeLoad": {
      "[the report](report.pdf)": "a → /view/papers/report.pdf",
      "![The report](report.pdf)": "pdf slot: link \"report.pdf\" → /view/papers/report.pdf",
      "<object data=\"report.pdf\">": "pdf slot: link \"report.pdf\" → /view/papers/report.pdf",
      "![[report.pdf]]": "pdf slot: link \"report.pdf\" → /view/papers/report.pdf",
      "[[report.pdf]]": "a → /view/papers/report.pdf",
      "![A scan](scan)": "img → /raw?path=papers%2Fscan"
    },
    "shown": {
      "[the report](report.pdf)": "a → /view/papers/report.pdf",
      "![The report](report.pdf)": "pdf slot: card ready, image /api/plugin/pdf/preview-image?key=preview-1, \"report.pdf · 1 page · View\", View → /view/papers/report.pdf",
      "<object data=\"report.pdf\">": "pdf slot: card ready, image /api/plugin/pdf/preview-image?key=preview-1, \"report.pdf · 1 page · View\", View → /view/papers/report.pdf",
      "![[report.pdf]]": "pdf slot: card ready, image /api/plugin/pdf/preview-image?key=preview-1, \"report.pdf · 1 page · View\", View → /view/papers/report.pdf",
      "[[report.pdf]]": "a → /view/papers/report.pdf",
      "![A scan](scan)": "img → /raw?path=papers%2Fscan"
    },
    "clicks": {
      "fallback": {
        "opened": true,
        "target": {
          "path": "papers/report.pdf"
        }
      },
      "view": {
        "opened": true,
        "target": {
          "path": "papers/report.pdf"
        }
      },
      "modified": {
        "opened": false
      }
    },
    "pluginLoads": {
      "calls": 3,
      "names": [
        "pdf"
      ]
    },
    "previewsAsked": [
      "/api/plugin/pdf/preview?path=papers%2Freport.pdf",
      "/api/plugin/pdf/preview?path=papers%2Freport.pdf",
      "/api/plugin/pdf/preview?path=papers%2Freport.pdf"
    ],
    "print": [
      "eager",
      "eager",
      "eager"
    ],
    "linkCards": [
      "the report: view revision papers/report.pdf",
      "View: view revision papers/report.pdf",
      "View: view revision papers/report.pdf",
      "View: view revision papers/report.pdf",
      "report.pdf: view revision papers/report.pdf"
    ],
    "disposal": {
      "cardsLeft": 0,
      "slots": 3,
      "linkCardsLeft": 0
    },
    "replacedBeforeLoad": {
      "asked": 0,
      "shows": {
        "![The report](report.pdf)": "pdf slot: link \"report.pdf\" → /view/papers/report.pdf",
        "<object data=\"report.pdf\">": "pdf slot: link \"report.pdf\" → /view/papers/report.pdf",
        "![[report.pdf]]": "pdf slot: link \"report.pdf\" → /view/papers/report.pdf"
      }
    },
    "withoutPlugin": {
      "![The report](report.pdf)": "pdf slot: link \"report.pdf\" → /view/papers/report.pdf",
      "<object data=\"report.pdf\">": "pdf slot: link \"report.pdf\" → /view/papers/report.pdf",
      "![[report.pdf]]": "pdf slot: link \"report.pdf\" → /view/papers/report.pdf"
    },
    "viewersDrawn": 0,
    "rawAddressesOfThePdf": 0
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
    "headings": [
      "# <span class=\"metabrowser-wiki-heading\" id=\"obsidian-heading-Guide\"></span>Guide",
      "## <span class=\"metabrowser-wiki-heading\" id=\"obsidian-heading-Guide#Setup\"></span><span class=\"metabrowser-wiki-heading\" id=\"obsidian-heading-Setup\"></span>Setup",
      "<span class=\"metabrowser-wiki-heading\" id=\"obsidian-heading-Usage\"></span>Usage",
      "=====",
      "- step",
      "---",
      "## <span class=\"metabrowser-wiki-heading\" id=\"obsidian-heading-Usage#Setup\"></span>Setup",
      ""
    ],
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
    "stagedDispatchOrder": [
      "outgoing embed 1",
      "staged document",
      "outgoing embed 2"
    ],
    "terminatedAfterLastRelease": true,
    "workersAfterRecovery": 2
  }
}
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
