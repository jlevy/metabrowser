---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: file preview lifecycle

These browserless sessions execute the complete production owners for asynchronous file
selection and incremental source loading.
They pin same-path request ownership, cache and validator commits, file-to-folder
replacement, dirty-marker preservation, failed renderer rollback, retry, and stale chunk
rejection without requiring a browser.

```console
$ node tests/dom/file-navigation-lazy-asset-session.js
{
  "dependencyFailure": {
    "error": "compositor unavailable",
    "status": "error"
  },
  "samePathRevalidation": {
    "cachedRevision": "B",
    "dirty": false,
    "etag": "\"B\"",
    "lateOlderCommit": "cancelled",
    "markerSharedByPendingRequests": true,
    "newerCommit": "file",
    "newerSettled": true,
    "olderAbort": {
      "status": "cancelled"
    },
    "replacementSawDirty": true
  },
  "fileToFolderEventRace": {
    "cacheRetained": false,
    "dirty": true,
    "etagRetained": false,
    "folderCommit": "folder",
    "olderMarkerSettled": false
  },
  "missingValidatorResponse": {
    "cachedRevision": "fresh",
    "dirty": false,
    "noValidatorCommit": "file",
    "noValidatorSettled": true,
    "validatorRetained": false
  },
  "boundedInvalidations": {
    "oldestRetained": false,
    "retained": [
      "two.md",
      "three.md"
    ],
    "size": 2
  },
  "authoritativeSnapshot": {
    "actions": [
      [
        "install",
        [
          "kept.jsonl",
          "new.jsonl",
          "src"
        ]
      ],
      [
        "retire",
        "gone.jsonl",
        false
      ],
      [
        "upsert",
        "kept.jsonl",
        true
      ],
      [
        "upsert",
        "new.jsonl",
        true
      ],
      [
        "upsert",
        "src",
        true
      ]
    ],
    "active": [
      "new.jsonl"
    ],
    "paths": [
      "kept.jsonl",
      "new.jsonl",
      "src"
    ],
    "renderedRows": {
      "kept.jsonl": {
        "children": [],
        "expanded": false
      },
      "src": {
        "children": [
          "src/lazy/deep.md"
        ],
        "expanded": true
      },
      "new.jsonl": {
        "children": [],
        "expanded": false
      }
    }
  }
}
```

```console
$ node tests/dom/source-append-navigation-session.js
{
  "afterFailedRender": {
    "cacheIsOriginal": true,
    "content": "old",
    "cursor": 3,
    "nextBytes": 128,
    "truncated": true
  },
  "afterRetryCommit": {
    "cacheIsOriginal": false,
    "content": "oldnew",
    "cursor": 6,
    "nextBytes": 256,
    "truncated": false
  },
  "samePathAba": {
    "committed": false,
    "content": "old",
    "nextBytes": null
  },
  "cacheReplacement": {
    "committed": false,
    "content": "replacement",
    "nextBytes": null
  }
}
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
