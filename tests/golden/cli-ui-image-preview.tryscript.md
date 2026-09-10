---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Image Preview

This browserless session crosses the production compositor into the lazily loaded image
renderer. It pins asset ordering, safe DOM construction, raw-path encoding, alternative
text, cancellation, replacement, error fallback, and idempotent disposal without relying
on browser paint.

```console
$ node tests/dom/image-preview-session.js
{
  "cancellation": {
    "cancelledBeforeSettle": true,
    "lateHandleDisposed": true,
    "status": "cancelled"
  },
  "composition": {
    "assetRequests": [
      "image",
      "image",
      "image"
    ],
    "cancelledPreparation": "cancelled",
    "initialView": "preview",
    "missingRenderer": true,
    "registeredAfterAssets": true
  },
  "disposal": {
    "activeContainerCount": 1,
    "idempotent": true,
    "secondDetached": true
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
    "alt": "images/<unsafe \"quoted\" & file>.png",
    "childCount": 1,
    "className": "file-image",
    "committed": true,
    "hasInlineHandler": false,
    "rawUrl": "/raw?path=images%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.png",
    "status": "mounted",
    "tagName": "IMG"
  },
  "innerHtmlWrites": 0,
  "replacement": {
    "committed": true,
    "firstDetached": true,
    "secondAlt": "next/diagram #2.svg",
    "secondRawUrl": "/raw?path=next%2Fdiagram%20%232.svg",
    "staleCommitRejected": true,
    "staleCommitPreservedReplacement": true,
    "status": "mounted"
  }
}
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
