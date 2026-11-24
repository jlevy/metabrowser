---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: PDF Preview

This browserless session crosses the production compositor into the lazily loaded PDF
renderer, and reads the SDK’s `host` and `capabilities()` accessors it decides by.
It pins the view for each host and trust profile: the macOS app’s descriptor or none,
and active content or inert.
The app gets Open, a link marked `data-metabrowser-open-file` with its subject, which
the app intercepts and opens in the default app for the type (the `open-file` action).
A browser gets Download and Open in new tab.
Every profile draws the same `<embed>`: the inert page’s policy admits an object from
`/raw` alone, so trust changes nothing here (`object-src` in
`capabilities.untrusted_content_security_policy`). It also pins the `/raw` address for a
folder path and a pinned revision’s GitPath wire, the download name, replacement, and
disposal. The browser painting the PDF is not modeled.

```console
$ node tests/dom/pdf-preview-session.js
{
  "composition": {
    "assetRequests": [
      "pdf"
    ],
    "initialView": "preview"
  },
  "disposal": {
    "emptied": true
  },
  "emptyPathError": "pdf preview requires a non-empty string path",
  "innerHtmlWrites": 0,
  "matrix": {
    "appActive": {
      "committed": true,
      "status": "mounted",
      "actions": [
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-metabrowser-open-file": "filesystem",
            "data-tip-text": "Open in the app this Mac uses for PDF files",
            "download": "<unsafe \"quoted\" & file>.pdf",
            "href": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf"
          },
          "text": "Open"
        },
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-tip-text": "Save a copy of this PDF",
            "download": "<unsafe \"quoted\" & file>.pdf",
            "href": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf"
          },
          "text": "Download"
        }
      ],
      "body": {
        "tag": "embed",
        "attributes": {
          "aria-label": "papers/<unsafe \"quoted\" & file>.pdf",
          "class": "pdf-viewer",
          "src": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf",
          "type": "application/pdf"
        }
      },
      "childCount": 2
    },
    "appInert": {
      "committed": true,
      "status": "mounted",
      "actions": [
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-metabrowser-open-file": "filesystem",
            "data-tip-text": "Open in the app this Mac uses for PDF files",
            "download": "<unsafe \"quoted\" & file>.pdf",
            "href": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf"
          },
          "text": "Open"
        },
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-tip-text": "Save a copy of this PDF",
            "download": "<unsafe \"quoted\" & file>.pdf",
            "href": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf"
          },
          "text": "Download"
        }
      ],
      "body": {
        "tag": "embed",
        "attributes": {
          "aria-label": "papers/<unsafe \"quoted\" & file>.pdf",
          "class": "pdf-viewer",
          "src": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf",
          "type": "application/pdf"
        }
      },
      "childCount": 2
    },
    "browserActive": {
      "committed": true,
      "status": "mounted",
      "actions": [
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-tip-text": "Save a copy of this PDF",
            "download": "<unsafe \"quoted\" & file>.pdf",
            "href": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf"
          },
          "text": "Download"
        },
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-tip-text": "Show this PDF in the browser's viewer, in its own tab",
            "href": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf",
            "rel": "noopener noreferrer",
            "target": "_blank"
          },
          "text": "Open in new tab"
        }
      ],
      "body": {
        "tag": "embed",
        "attributes": {
          "aria-label": "papers/<unsafe \"quoted\" & file>.pdf",
          "class": "pdf-viewer",
          "src": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf",
          "type": "application/pdf"
        }
      },
      "childCount": 2
    },
    "browserInert": {
      "committed": true,
      "status": "mounted",
      "actions": [
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-tip-text": "Save a copy of this PDF",
            "download": "<unsafe \"quoted\" & file>.pdf",
            "href": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf"
          },
          "text": "Download"
        },
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-tip-text": "Show this PDF in the browser's viewer, in its own tab",
            "href": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf",
            "rel": "noopener noreferrer",
            "target": "_blank"
          },
          "text": "Open in new tab"
        }
      ],
      "body": {
        "tag": "embed",
        "attributes": {
          "aria-label": "papers/<unsafe \"quoted\" & file>.pdf",
          "class": "pdf-viewer",
          "src": "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf",
          "type": "application/pdf"
        }
      },
      "childCount": 2
    }
  },
  "pinned": {
    "app": {
      "committed": true,
      "status": "mounted",
      "actions": [
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-metabrowser-open-file": "git_revision",
            "data-tip-text": "Open in the app this Mac uses for PDF files",
            "download": "report.pdf",
            "href": "/raw?path=g1-cGFwZXJz%2Fg1-cmVwb3J0LnBkZg"
          },
          "text": "Open"
        },
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-tip-text": "Save a copy of this PDF",
            "download": "report.pdf",
            "href": "/raw?path=g1-cGFwZXJz%2Fg1-cmVwb3J0LnBkZg"
          },
          "text": "Download"
        }
      ],
      "body": {
        "tag": "embed",
        "attributes": {
          "aria-label": "papers/report.pdf",
          "class": "pdf-viewer",
          "src": "/raw?path=g1-cGFwZXJz%2Fg1-cmVwb3J0LnBkZg",
          "type": "application/pdf"
        }
      },
      "childCount": 2
    },
    "browser": {
      "committed": true,
      "status": "mounted",
      "actions": [
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-tip-text": "Save a copy of this PDF",
            "download": "report.pdf",
            "href": "/raw?path=g1-cGFwZXJz%2Fg1-cmVwb3J0LnBkZg"
          },
          "text": "Download"
        },
        {
          "tag": "a",
          "attributes": {
            "class": "pdf-action",
            "data-tip-text": "Show this PDF in the browser's viewer, in its own tab",
            "href": "/raw?path=g1-cGFwZXJz%2Fg1-cmVwb3J0LnBkZg",
            "rel": "noopener noreferrer",
            "target": "_blank"
          },
          "text": "Open in new tab"
        }
      ],
      "body": {
        "tag": "embed",
        "attributes": {
          "aria-label": "papers/report.pdf",
          "class": "pdf-viewer",
          "src": "/raw?path=g1-cGFwZXJz%2Fg1-cmVwb3J0LnBkZg",
          "type": "application/pdf"
        }
      },
      "childCount": 2
    }
  },
  "replacement": {
    "firstDetached": true,
    "firstReleasedSrc": true,
    "hostHoldsOne": true
  },
  "sdkAccessors": {
    "capabilities": {
      "active": {
        "activeContent": true,
        "mutations": false
      },
      "frozen": true,
      "inert": {
        "activeContent": false,
        "mutations": false
      },
      "missing": {
        "activeContent": false,
        "mutations": false
      }
    },
    "host": {
      "app": {
        "actions": [
          "open-file"
        ],
        "openFile": true
      },
      "browser": {
        "actions": [],
        "openFile": false
      },
      "malformed": {
        "actions": [],
        "openFile": false
      },
      "mixed": {
        "actions": [
          "reveal-file"
        ],
        "openFile": false
      }
    }
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
