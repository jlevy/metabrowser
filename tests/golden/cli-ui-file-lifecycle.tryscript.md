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

## Preview pane states

The preview pane shows a loading indicator while a selection loads, including the root
landing, and then the selected view; an empty folder settles as content, not an error.
“Select a file to preview.”
appears only when nothing is selected and nothing is loading.
A navigation tab switch makes no claim, so the selection loading underneath it still
lands. A rejected fetch is a connection state with its own wording, distinct from HTTP
and renderer errors, and the inventory stream reopening retries only the selection that
failed that way.

```console
$ node tests/dom/preview-pane-state-session.js
{
  "rootLanding": {
    "afterSettle": {
      "paint": "none"
    },
    "settled": true,
    "shipped": {
      "paint": "loading",
      "subject": "preview"
    },
    "snapshot": {
      "claim": 1,
      "owner": "file",
      "path": "",
      "phase": "content"
    },
    "target": {
      "path": ""
    },
    "whileLoading": {
      "paint": "loading",
      "subject": "folder"
    }
  },
  "loadingToContent": {
    "afterSettle": {
      "paint": "none"
    },
    "settled": true,
    "snapshot": {
      "claim": 1,
      "owner": "file",
      "path": "docs/guide.md",
      "phase": "content"
    },
    "whileLoading": {
      "paint": "loading",
      "subject": "file"
    }
  },
  "loadingToEmptyFolder": {
    "afterSettle": {
      "paint": "none"
    },
    "response": {
      "cacheRetained": false,
      "commit": "folder"
    },
    "settled": true,
    "snapshot": {
      "claim": 1,
      "owner": "file",
      "path": "empty",
      "phase": "content"
    },
    "whileLoading": {
      "paint": "loading",
      "subject": "folder"
    }
  },
  "panelSwitchDuringLoad": {
    "afterSettle": {
      "claim": 1,
      "owner": "file",
      "path": "big",
      "phase": "content"
    },
    "afterSwitch": {
      "paint": "loading",
      "subject": "folder"
    },
    "beforeSwitch": {
      "paint": "loading",
      "subject": "folder"
    },
    "claimCurrentAfterSwitch": true,
    "settled": true,
    "supersededByAnotherOwner": {
      "fileClaimCurrent": false,
      "gitClaimCurrent": true,
      "lateFilePlaceholder": {
        "paint": "none"
      },
      "lateFileSettled": false,
      "reconnectRetry": null,
      "snapshot": {
        "claim": 2,
        "owner": "git",
        "path": null,
        "phase": "external"
      }
    }
  },
  "landingWithoutSelection": {
    "abandonedLoadCurrent": false,
    "abandonedLoadSettled": false,
    "commitRouteWithoutOwner": {
      "snapshot": {
        "claim": 1,
        "owner": "none",
        "path": null,
        "phase": "idle"
      },
      "unclaimed": {
        "message": "Select a file to preview.",
        "paint": "idle"
      }
    },
    "commitRouteWithOwner": {
      "snapshot": {
        "claim": 1,
        "owner": "git",
        "path": null,
        "phase": "external"
      },
      "unclaimed": {
        "paint": "none"
      }
    },
    "idle": {
      "message": "Select a file to preview.",
      "paint": "idle"
    },
    "snapshot": {
      "claim": 2,
      "owner": "none",
      "path": null,
      "phase": "idle"
    }
  },
  "failures": {
    "abortPassesThrough": true,
    "aborted": {
      "outcome": {
        "status": "cancelled"
      },
      "revalidated": [],
      "shown": [],
      "snapshot": {
        "claim": 1,
        "owner": "file",
        "path": "left.md",
        "phase": "loading"
      }
    },
    "fetchRejectionName": "ServerUnreachableError",
    "fetchRejectionPreservesCause": "Failed to fetch",
    "httpNotFound": {
      "outcome": {
        "message": "gone.md is no longer available.",
        "status": "not-found"
      },
      "revalidated": [],
      "shown": [
        {
          "detail": "This file is no longer available.",
          "kind": "error",
          "summary": "Could not open this file."
        }
      ],
      "reconnectRetry": null,
      "snapshot": {
        "claim": 1,
        "owner": "file",
        "path": "gone.md",
        "phase": "error"
      }
    },
    "httpServerError": {
      "outcome": {
        "message": "Could not open broken.md. Check that the file still exists and is readable.",
        "status": "error"
      },
      "revalidated": [],
      "shown": [
        {
          "detail": "The request failed (HTTP 500).",
          "kind": "error",
          "summary": "Could not open this file."
        }
      ],
      "snapshot": {
        "claim": 1,
        "owner": "file",
        "path": "broken.md",
        "phase": "error"
      }
    },
    "markedOnce": true,
    "quickFile": {
      "opaqueThrow": {
        "message": "Could not open this file. Try again.",
        "status": "error"
      },
      "unreachableThrow": {
        "message": "Metabrowser isn’t reachable. It may have stopped. Start it again with metab <folder>, and this page will reconnect.",
        "status": "unreachable"
      }
    },
    "rendererTypeError": {
      "outcome": {
        "message": "Could not open odd.md. Check that the file still exists and is readable.",
        "status": "error"
      },
      "revalidated": [],
      "shown": [
        {
          "detail": "Cannot read properties of undefined (reading 'views')",
          "kind": "error",
          "summary": "Could not open this file."
        }
      ],
      "snapshot": {
        "claim": 1,
        "owner": "file",
        "path": "odd.md",
        "phase": "error"
      }
    },
    "serverUnreachable": {
      "outcome": {
        "message": "Metabrowser isn’t reachable. It may have stopped. Start it again with metab <folder>, and this page will reconnect.",
        "status": "unreachable"
      },
      "revalidated": [
        "empty"
      ],
      "shown": [
        {
          "detail": "It may have stopped. Start it again with metab <folder>, and this page will reconnect.",
          "kind": "unreachable",
          "summary": "Metabrowser isn’t reachable."
        }
      ],
      "snapshot": {
        "claim": 1,
        "owner": "file",
        "path": "empty",
        "phase": "unreachable"
      }
    }
  },
  "recoveryOnReconnect": {
    "afterRecovery": null,
    "beforeFailure": null,
    "duplicateOpen": null,
    "failedLoadCurrent": false,
    "movedOnRetry": null,
    "retry": {
      "folder": true,
      "path": "empty",
      "viewId": "overview"
    },
    "settled": true,
    "snapshot": {
      "claim": 2,
      "owner": "file",
      "path": "empty",
      "phase": "content"
    },
    "whileRetrying": {
      "paint": "loading",
      "subject": "folder"
    }
  }
}
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
