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
A rejected fetch, or a body read that fails after the headers arrived, is a connection
state with its own wording, distinct from HTTP, malformed-body, and renderer errors.

The `shell` scenarios run the `app.js` functions that compose those decisions with the
real navigation controller.
A Files to Git to Files tab switch keeps the loading claim, and the folder still lands.
The panels share one scroller, and each keeps its own place in it: a switch saves the
offset of the panel it leaves, puts back the offset of the one it shows, or the top for
a panel never shown, and tells the panel that leaves.
Files and Pulls return to what they last showed.
A switch to Commits, the first or a later one, pushes the neutral entry and asks the Git
panel to land, which selects the newest commit and replaces the entry with its address;
Commits starts from its top, and the shell paints no prompt over the pane while it
waits. The heading at the top of the nav goes home from any tab, in the page: a plain
click, or Enter on the link, opens the served root in Files at the top of its panel and
pushes one entry, none when Files already shows the root, and Back returns to the tab
the reader left. A modified or middle click is left to the browser.
Before the tab controller has loaded, Files in front opens the root with the tree at its
top, on the root already shown too; a pull request’s page fetches the controller first,
and a later open wins.
Opening a path again after it failed, or after a Git commit replaced it, loads it again,
while re-opening a path the pane already shows only delivers its fragment.
The inventory stream’s `onopen` retries only a selection that failed as unreachable, and
because `selectFile` claims before its first `await`, a duplicate open does not retry
twice. The startup settle shows the prompt only for a `/commit/` route or the neutral
Commits entry that no Git view claimed.
An address with a line anchor or `plain=1` opens its file in the Source view, and any
other fragment or query in the file’s default view; a line anchor added to the file
already shown selects its Source tab without loading the file again.
A view that plugin navigation names outright wins over the address’s.

The asset loader and the plugin SDK in these scenarios are the production scripts, and
what they fetch on demand is the production file, delivered a turn after it is asked
for. A page that loads at a line-anchored address waits for the module that reads the
anchor, which arrives with the view compositor, and opens the Source view.
That fetch overlaps revealing the row, and a plain address asks for nothing first.
The pull-request page’s routes are a startup script of a pull-request address only: a
folder’s addresses never ask for them, and a history landing on a page’s address fetches
them and then mounts the page.
When on-demand code does not arrive, the pane says that: a failed file, or a
pull-request page that could not load, never the prompt to select a file or the message
that no plugin renders the page.
Asking again fetches only what failed.

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
  },
  "holdsSelection": {
    "afterFileError": false,
    "afterGitClaim": false,
    "afterUnreachable": false,
    "beforeAnyClaim": false,
    "otherPathWhileLoading": false,
    "whileLoading": true,
    "withContent": true
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
    "bodyRead": {
      "abortPassesThrough": true,
      "interruptedName": "ServerUnreachableError",
      "interruptedPreservesCause": "terminated",
      "malformedJsonPassesThrough": true,
      "markedOnce": true
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
        "message": "Metabrowser is not reachable. It may have stopped. Start it again with metab <folder>, and this page will reconnect.",
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
        "message": "Metabrowser is not reachable. It may have stopped. Start it again with metab <folder>, and this page will reconnect.",
        "status": "unreachable"
      },
      "revalidated": [
        "empty"
      ],
      "shown": [
        {
          "detail": "It may have stopped. Start it again with metab <folder>, and this page will reconnect.",
          "kind": "unreachable",
          "summary": "Metabrowser is not reachable."
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
  "shell": {
    "shippedPlaceholderHtml": "<div class=\"loading mb-delayed-loading\"><div class=\"spinner\"></div><span class=\"sr-only\">Loading preview…</span></div>",
    "tabSwitchDuringLoad": {
      "backOnFilesTab": {
        "pane": {
          "claim": 1,
          "owner": "file",
          "path": "big",
          "phase": "loading",
          "shows": "loading mb-delayed-loading: Loading preview…"
        },
        "tabs": [
          "files:",
          "git:none"
        ]
      },
      "landed": {
        "claim": 1,
        "owner": "file",
        "path": "big",
        "phase": "content",
        "shows": "rendered-view: folder big"
      },
      "loading": {
        "claim": 1,
        "owner": "file",
        "path": "big",
        "phase": "loading",
        "shows": "loading mb-delayed-loading: Loading preview…"
      },
      "onGitTab": {
        "pane": {
          "claim": 1,
          "owner": "file",
          "path": "big",
          "phase": "loading",
          "shows": "loading mb-delayed-loading: Loading preview…"
        },
        "tabs": [
          "files:none",
          "git:"
        ]
      },
      "panelShows": [
        "git first show",
        "git show"
      ]
    },
    "navPanelsKeepTheirPlace": {
      "switches": [
        "scrolled to 400, git chosen: shows 0",
        "scrolled to 250, files chosen: shows 400",
        "scrolled to 400, git chosen: shows 250",
        "scrolled to 250, git chosen: shows 250"
      ],
      "told": [
        "git hidden"
      ]
    },
    "independentMainTabs": {
      "selections": [
        {
          "address": "/pulls",
          "panel": "pulls",
          "owner": "pull-request",
          "scroll": 0
        },
        {
          "address": "/commit/cccccccccccccccccccccccccccccccccccccccc",
          "panel": "git",
          "owner": "git",
          "scroll": 0
        },
        {
          "address": "/pulls?state=closed",
          "panel": "pulls",
          "owner": "pull-request",
          "scroll": 80
        },
        {
          "address": "/view/notes.md?plain=1#L2",
          "panel": "files",
          "owner": "file",
          "scroll": 240
        },
        {
          "address": "/pull/7/files/src/a.py",
          "panel": "pulls",
          "owner": "pull-request",
          "scroll": 80
        },
        {
          "address": "/commit/cccccccccccccccccccccccccccccccccccccccc",
          "panel": "git",
          "owner": "git",
          "scroll": 0
        }
      ],
      "historyPushes": 6,
      "activeAfterHistory": "pulls",
      "commitLandings": [
        "newest",
        "newest",
        "newest"
      ]
    },
    "mainTabShortcuts": {
      "tabOrder": [
        "files",
        "pulls",
        "git"
      ],
      "ariaKeys": [
        "F",
        "R",
        "H"
      ],
      "keyboardRoutes": [
        "/pulls",
        "/view/",
        "/view/"
      ]
    },
    "goingHome": {
      "the page opens on a file, its tree scrolled": {
        "address": "/view/notes.md",
        "state": null,
        "tab": "files",
        "pane": "file \"notes.md\"",
        "scroll": 240,
        "pushes": 0
      },
      "Commits, before a commit is selected": {
        "address": "/view/",
        "state": {
          "gitLanding": true
        },
        "tab": "git",
        "pane": "none",
        "scroll": 0,
        "pushes": 1
      },
      "home from Commits": {
        "kept": true,
        "address": "/view/",
        "state": null,
        "tab": "files",
        "pane": "file \"\"",
        "scroll": 0,
        "pushes": 2
      },
      "Back from home": {
        "address": "/view/",
        "state": {
          "gitLanding": true
        },
        "tab": "git",
        "pane": "none",
        "scroll": 0,
        "pushes": 2
      },
      "a commit's entry": {
        "address": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "state": null,
        "tab": "git",
        "pane": "git",
        "scroll": 0,
        "pushes": 2
      },
      "home from a commit": {
        "kept": true,
        "address": "/view/",
        "state": null,
        "tab": "files",
        "pane": "file \"\"",
        "scroll": 0,
        "pushes": 3
      },
      "Pulls": {
        "address": "/pulls",
        "state": null,
        "tab": "pulls",
        "pane": "pull-request",
        "scroll": 0,
        "pushes": 4
      },
      "home from Pulls": {
        "kept": true,
        "address": "/view/",
        "state": null,
        "tab": "files",
        "pane": "file \"\"",
        "scroll": 0,
        "pushes": 5
      },
      "home on the root it shows": {
        "kept": true,
        "address": "/view/",
        "state": null,
        "tab": "files",
        "pane": "file \"\"",
        "scroll": 0,
        "pushes": 5
      },
      "a click the browser keeps": {
        "Command": "left to the browser",
        "Control": "left to the browser",
        "Shift": "left to the browser",
        "Option": "left to the browser",
        "middle button": "left to the browser",
        "already handled": "left to the browser"
      },
      "before the tab controller loads": {
        "Files in front": {
          "address": "/view/",
          "scrollAfterHome": {
            "from 300": 0,
            "on the root, from 180": 0
          },
          "tabScript": 0
        },
        "a pull request in front": {
          "address": "/view/",
          "tab": "files",
          "tabScript": 1
        },
        "a later open while it loads": "/view/notes.md"
      }
    },
    "quickSearchPullRoute": {
      "opened": [
        "/pull/307"
      ],
      "backTo": "/view/notes.md?plain=1#L2",
      "superseded": "cancelled"
    },
    "reselectAfterFailure": {
      "afterGitClaim": {
        "fetches": 2,
        "fragments": 6,
        "outcome": {
          "status": "opened",
          "focusesPreview": true
        },
        "pane": {
          "claim": 8,
          "owner": "file",
          "path": "notes.md",
          "phase": "content",
          "shows": "rendered-view: text notes.md"
        }
      },
      "fileError": {
        "fetches": 1,
        "fragments": 3,
        "outcome": {
          "message": "Could not open broken.md. Check that the file still exists and is readable.",
          "status": "error",
          "focusesPreview": false
        },
        "pane": {
          "claim": 4,
          "owner": "file",
          "path": "broken.md",
          "phase": "error",
          "shows": "preview-empty preview-error: Could not open this file. The request failed (HTTP 500)."
        }
      },
      "reopenedContent": {
        "fetches": 2,
        "fragments": 3,
        "outcome": {
          "status": "opened",
          "focusesPreview": true
        },
        "pane": {
          "claim": 3,
          "owner": "file",
          "path": "notes.md",
          "phase": "content",
          "shows": "rendered-view: text notes.md"
        }
      },
      "retriedFileError": {
        "fetches": 2,
        "fragments": 4,
        "outcome": {
          "status": "opened",
          "focusesPreview": true
        },
        "pane": {
          "claim": 5,
          "owner": "file",
          "path": "broken.md",
          "phase": "content",
          "shows": "rendered-view: text broken.md"
        }
      },
      "retriedUnreachable": {
        "fetches": 2,
        "fragments": 2,
        "outcome": {
          "status": "opened",
          "focusesPreview": true
        },
        "pane": {
          "claim": 3,
          "owner": "file",
          "path": "notes.md",
          "phase": "content",
          "shows": "rendered-view: text notes.md"
        }
      },
      "unreachable": {
        "fetches": 1,
        "fragments": 1,
        "outcome": {
          "message": "Metabrowser is not reachable. It may have stopped. Start it again with metab <folder>, and this page will reconnect.",
          "status": "unreachable",
          "focusesPreview": false
        },
        "pane": {
          "claim": 2,
          "owner": "file",
          "path": "notes.md",
          "phase": "unreachable",
          "shows": "preview-empty preview-error: Metabrowser is not reachable. It may have stopped. Start it again with metab &lt;folder&gt;, and this page will reconnect."
        }
      }
    },
    "bodyReadFailure": {
      "interruptedJsonBody": {
        "outcome": {
          "message": "Metabrowser is not reachable. It may have stopped. Start it again with metab <folder>, and this page will reconnect.",
          "status": "unreachable",
          "focusesPreview": false
        },
        "pane": {
          "claim": 2,
          "owner": "file",
          "path": "big.log",
          "phase": "unreachable",
          "shows": "preview-empty preview-error: Metabrowser is not reachable. It may have stopped. Start it again with metab &lt;folder&gt;, and this page will reconnect."
        },
        "reconnectRetry": {
          "folder": false,
          "path": "big.log"
        }
      },
      "interruptedErrorBody": {
        "outcome": {
          "message": "Metabrowser is not reachable. It may have stopped. Start it again with metab <folder>, and this page will reconnect.",
          "status": "unreachable",
          "focusesPreview": false
        },
        "pane": {
          "claim": 3,
          "owner": "file",
          "path": "failing.md",
          "phase": "unreachable",
          "shows": "preview-empty preview-error: Metabrowser is not reachable. It may have stopped. Start it again with metab &lt;folder&gt;, and this page will reconnect."
        },
        "reconnectRetry": {
          "folder": false,
          "path": "failing.md"
        }
      },
      "malformedJson": {
        "outcome": {
          "message": "Could not open garbled.json. Check that the file still exists and is readable.",
          "status": "error",
          "focusesPreview": false
        },
        "pane": {
          "claim": 4,
          "owner": "file",
          "path": "garbled.json",
          "phase": "error",
          "shows": "preview-empty preview-error: Could not open this file. Unexpected token &lt; in JSON at position 0"
        },
        "reconnectRetry": null
      }
    },
    "reconnectRetry": {
      "afterGitClaim": {
        "fetches": 1,
        "pane": {
          "claim": 2,
          "owner": "git",
          "path": null,
          "phase": "external",
          "shows": "git-commit: abc123"
        }
      },
      "catalogFeedStarts": 2,
      "claimedByOpen": {
        "claim": 2,
        "owner": "file",
        "path": "empty",
        "phase": "loading",
        "shows": "preview-empty preview-error: Metabrowser is not reachable. It may have stopped. Start it again with metab &lt;folder&gt;, and this page will reconnect."
      },
      "failed": {
        "claim": 1,
        "owner": "file",
        "path": "empty",
        "phase": "unreachable",
        "shows": "preview-empty preview-error: Metabrowser is not reachable. It may have stopped. Start it again with metab &lt;folder&gt;, and this page will reconnect."
      },
      "fetchesForFailedFolder": 2,
      "paletteReconnects": 2,
      "recovered": {
        "claim": 2,
        "owner": "file",
        "path": "empty",
        "phase": "content",
        "shows": "rendered-view: folder empty"
      },
      "streamUrl": "/api/events?scope=root-depth-2",
      "whileRetrying": {
        "claim": 2,
        "owner": "file",
        "path": "empty",
        "phase": "loading",
        "shows": "loading mb-delayed-loading: Loading folder…"
      }
    },
    "startupSettle": {
      "commitRouteWithGitOwner": {
        "claim": 1,
        "owner": "git",
        "path": null,
        "phase": "external",
        "shows": "git-commit: abc123"
      },
      "commitRouteWithoutOwner": {
        "claim": 1,
        "owner": "none",
        "path": null,
        "phase": "idle",
        "shows": "preview-empty: Select a file to preview."
      },
      "locationWithoutSelection": {
        "claim": 1,
        "owner": "none",
        "path": null,
        "phase": "idle",
        "shows": "preview-empty: Select a file to preview."
      },
      "viewRoute": {
        "afterSelection": {
          "claim": 1,
          "owner": "file",
          "path": "docs/guide.md",
          "phase": "content",
          "shows": "rendered-view: text docs/guide.md"
        },
        "beforeSelection": {
          "claim": 0,
          "owner": "shell",
          "path": null,
          "phase": "starting",
          "shows": "loading mb-delayed-loading: Loading preview…"
        }
      }
    },
    "anchoredAddressesOpenSource": {
      "renderedViews": [
        "README.md: source",
        "guide.md: source",
        "notes.md: default view",
        "other.md: default view",
        "chosen.md: rendered"
      ],
      "tabClicks": [
        "notes.md: source"
      ],
      "fragments": 8
    },
    "coldAnchoredAddress": {
      "lineAnchorsAtStartup": "undefined",
      "scriptRequests": [
        "view-composition.js",
        "plugin-sdk-views.js"
      ],
      "renderedViews": [
        "a.py: source"
      ],
      "pane": {
        "claim": 1,
        "owner": "file",
        "path": "a.py",
        "phase": "content",
        "shows": "rendered-view: text a.py"
      },
      "whileTheRowIsRevealed": {
        "anchoredAddress": {
          "requestedMeanwhile": [
            "view-composition.js",
            "plugin-sdk-views.js"
          ],
          "renderedViews": [
            "a.py: source"
          ]
        },
        "plainAddress": {
          "requestedMeanwhile": [],
          "renderedViews": [
            "a.py: default view"
          ]
        }
      }
    },
    "pullRouteLoadsOnDemand": {
      "folderAddresses": {
        "scriptRequests": [
          "view-composition.js",
          "plugin-sdk-views.js"
        ],
        "hostCreated": false
      },
      "pullAddress": {
        "scriptRequests": [
          "plugin-sdk-views.js",
          "vendor/mustache.min.js"
        ],
        "pane": {
          "claim": 1,
          "owner": "pull-request",
          "path": null,
          "phase": "external",
          "shows": "preview-empty: No plugin renders pull-request pages here."
        },
        "afterTabLanding": {
          "scriptRequests": [
            "plugin-sdk-views.js",
            "vendor/mustache.min.js"
          ]
        }
      },
      "notAPullAddress": {
        "scriptRequests": [
          "pull-route.js"
        ],
        "pane": {
          "claim": 1,
          "owner": "none",
          "path": null,
          "phase": "idle",
          "shows": "preview-empty: Select a file to preview."
        }
      },
      "historyLandingWithoutHost": {
        "before": {
          "scriptRequests": [],
          "hostCreated": false
        },
        "scriptRequests": [
          "pull-route.js",
          "plugin-sdk-views.js",
          "vendor/mustache.min.js"
        ],
        "pane": {
          "claim": 2,
          "owner": "pull-request",
          "path": null,
          "phase": "external",
          "shows": "preview-empty: No plugin renders pull-request pages here."
        }
      }
    },
    "onDemandCodeRefused": {
      "viewHelpersOpeningAFile": {
        "failed": {
          "pane": {
            "claim": 1,
            "owner": "file",
            "path": "notes.md",
            "phase": "error",
            "shows": "preview-empty preview-error: Could not open this file. Failed to load asset: /static/plugin-sdk-views.js"
          },
          "scriptRequests": [
            "view-composition.js",
            "plugin-sdk-views.js"
          ]
        },
        "reopened": {
          "outcome": {
            "status": "opened",
            "focusesPreview": true
          },
          "pane": {
            "claim": 2,
            "owner": "file",
            "path": "notes.md",
            "phase": "content",
            "shows": "rendered-view: text notes.md"
          },
          "scriptRequests": [
            "plugin-sdk-views.js"
          ]
        }
      },
      "pullRoutesAtAPullAddress": {
        "pane": {
          "claim": 1,
          "owner": "pull-request",
          "path": null,
          "phase": "external",
          "shows": "preview-empty preview-error: Could not load the pull-request page. Refresh the page to try again."
        },
        "scriptRequests": [
          "pull-route.js"
        ]
      },
      "pullRoutesOnAHistoryLanding": {
        "pane": {
          "claim": 3,
          "owner": "pull-request",
          "path": null,
          "phase": "external",
          "shows": "preview-empty preview-error: Could not load the pull-request page. Refresh the page to try again."
        },
        "scriptRequests": [
          "pull-route.js"
        ]
      },
      "templatesOnThePullPage": {
        "failed": {
          "pane": {
            "claim": 1,
            "owner": "pull-request",
            "path": null,
            "phase": "external",
            "shows": "preview-empty preview-error: Could not load the pull-request page. Refresh the page to try again."
          },
          "scriptRequests": [
            "plugin-sdk-views.js",
            "vendor/mustache.min.js"
          ]
        },
        "nextRoute": {
          "pane": {
            "claim": 3,
            "owner": "pull-request",
            "path": null,
            "phase": "external",
            "shows": "preview-empty: No plugin renders pull-request pages here."
          },
          "scriptRequests": [
            "vendor/mustache.min.js"
          ]
        }
      },
      "viewHelpersOnThePullPage": {
        "failed": {
          "pane": {
            "claim": 1,
            "owner": "pull-request",
            "path": null,
            "phase": "external",
            "shows": "preview-empty preview-error: Could not load the pull-request page. Refresh the page to try again."
          },
          "scriptRequests": [
            "plugin-sdk-views.js",
            "vendor/mustache.min.js"
          ]
        },
        "nextRoute": {
          "pane": {
            "claim": 3,
            "owner": "pull-request",
            "path": null,
            "phase": "external",
            "shows": "preview-empty: No plugin renders pull-request pages here."
          },
          "scriptRequests": [
            "plugin-sdk-views.js"
          ]
        }
      }
    }
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
