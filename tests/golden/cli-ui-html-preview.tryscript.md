---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: HTML Preview

This browserless session crosses the production compositor into the lazily loaded HTML
preview renderer. It pins asset ordering, path-shaped `/raw` URLs, the iframe sandbox
token set, cancellation, replacement, error fallback, and idempotent disposal without
relying on browser paint.

```console
$ node tests/dom/html-preview-session.js
{
  "cancellation": {
    "cancelledBeforeSettle": true,
    "lateHandleDisposed": true,
    "status": "cancelled"
  },
  "composition": {
    "assetRequests": [
      "html",
      "html",
      "html"
    ],
    "cancelledPreparation": "cancelled",
    "initialView": "preview",
    "missingRenderer": true,
    "registeredAfterAssets": true,
    "sourceRegistered": true
  },
  "disposal": {
    "activeContainerCount": 1,
    "idempotent": true,
    "secondDetached": true,
    "secondSrcCleared": true
  },
  "error": {
    "accessible": true,
    "committed": true,
    "logged": [
      "broken renderer"
    ],
    "status": "error"
  },
  "firstMount": {
    "childCount": 1,
    "className": "file-html-preview",
    "committed": true,
    "hasAllowSameOrigin": false,
    "hasAllowTopNavigation": false,
    "hasInlineHandler": false,
    "rawUrl": "/raw/docs/%3Cunsafe%20%22quoted%22%20%26%20file%3E.html",
    "referrerPolicy": "no-referrer",
    "sandbox": "allow-scripts allow-popups allow-forms allow-downloads",
    "status": "mounted",
    "tagName": "IFRAME",
    "title": "docs/<unsafe \"quoted\" & file>.html"
  },
  "innerHtmlWrites": 0,
  "replacement": {
    "committed": true,
    "firstDetached": true,
    "secondRawUrl": "/raw/docs/100%25.html",
    "staleCommitRejected": true,
    "staleCommitPreservedReplacement": true,
    "status": "mounted"
  }
}
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
