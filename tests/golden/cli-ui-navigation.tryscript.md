---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: browserless navigation behavior

This session runs the exact production filter-control transition, request launch,
complete-leaf projection, and Recent tree model from a command line.
It covers the composition that isolated route and JavaScript unit tests missed: several
matching folders are explicitly collapsed, their descendants remain in the model handed
to the renderer, and a nonmatching leaf is removed before clustering.
The same session pins Recent continuity and live-batch composition: deep and subtree
invalidation, request coordination across the first sentinel and reconnect, expiry
during commit, capped-page repair, ambiguous unseen changes, retained-page lower bounds,
fixed-window coalescing, bounded retry recovery, and exact Quick File removal for deep
file-to-directory and file-to-symlink replacements with an immediate safe Recent tally.
It also pins the visible lower-bound wording after a deep change invalidates an
originally complete Recent page, rejects queued repaints after source or selection
changes, and repairs both active and settled Recent state after a stream resync.

The folder rows must still exist with their full matching counts.
DOM child presence is not part of the model.

```console
$ node tests/dom/recent-filter-session.js
{
  "request": "/api/recent?window=1h&limit=5000&types=.md",
  "matchingFiles": [
    "alpha/a.md",
    "alpha/b.md",
    "bravo/a.md",
    "bravo/b.md",
    "charlie/a.md",
    "charlie/b.md"
  ],
  "defaultExpanded": [],
  "selectedCount": 6,
  "rootNodeCount": 3,
  "rootNodes": [
    {
      "path": "alpha",
      "files": 2,
      "expanded": false,
      "childrenInModel": 2
    },
    {
      "path": "bravo",
      "files": 2,
      "expanded": false,
      "childrenInModel": 2
    },
    {
      "path": "charlie",
      "files": 2,
      "expanded": false,
      "childrenInModel": 2
    }
  ],
  "continuity": {
    "recomputeTransitions": {
      "source": {
        "schedule": "scheduled",
        "cancelled": true,
        "rendersAfterLateTimer": 0
      },
      "window": {
        "schedule": "scheduled",
        "rendersAfterLateTimer": 0
      },
      "filter": {
        "schedule": "scheduled",
        "cancelled": true,
        "rendersAfterLateTimer": 0
      },
      "current": {
        "schedule": "scheduled",
        "renders": [
          {
            "windowKey": "1h",
            "requestKey": "/api/recent?window=1h&limit=5000&types=.py"
          }
        ],
        "pending": false
      },
      "replacementOwnership": {
        "eventAfterStart": {
          "schedule": "scheduled",
          "renders": 0
        },
        "expiryAfterStart": {
          "mayPaint": false
        },
        "eventAfterFailure": {
          "schedule": "scheduled",
          "renders": 0
        },
        "sameSelectionRepair": {
          "schedule": "scheduled",
          "renderedRequest": {
            "windowKey": "24h",
            "requestKey": "/api/recent?window=24h&limit=5000&types=.md"
          }
        }
      }
    },
    "resync": {
      "activeRequest": {
        "invalidation": "dirty",
        "settle": "repair-scheduled",
        "commitCalled": false,
        "repairPending": true
      },
      "settledView": {
        "requestDisposition": "commit",
        "invalidation": "repair",
        "timerCount": 1,
        "delayMs": 100,
        "run": "repair",
        "fetches": [
          {
            "windowKey": "1h",
            "preserveRows": true
          }
        ]
      }
    },
    "untruncatedDeepUpsert": {
      "event": {
        "upserts": [
          {
            "p": "runs/day/job/changed.md",
            "e": ".md"
          }
        ],
        "removes": [],
        "remove_files": []
      },
      "recentEffect": {
        "changed": true,
        "needsAuthoritativeRepair": true,
        "removedEntries": 1,
        "retainedLowerBound": 1
      },
      "recentPaths": [
        "keep.md"
      ],
      "tally": "Filtered to 1+ files."
    },
    "nonFileReplacement": {
      "event": {
        "upserts": [],
        "removes": [],
        "remove_files": [],
        "non_file_paths": [
          "runs/day/job/replaced-dir",
          "runs/day/job/replaced-link"
        ]
      },
      "recentEffect": {
        "changed": true,
        "needsAuthoritativeRepair": true,
        "removedEntries": 2,
        "retainedLowerBound": 1
      },
      "recentPaths": [
        "runs/day/job/replaced-dir/child.md"
      ],
      "quickFilePaths": [
        "runs/day/job/replaced-dir/child.md"
      ]
    },
    "deepCatalogChangeNeedsRepair": true,
    "deepDirectoryReplacementNeedsRepair": true,
    "deepSymlinkReplacementNeedsRepair": true,
    "shallowNonFileReplacementNeedsRepair": false,
    "shallowSubtreeRemovalNeedsRepair": true,
    "firstSentinelAfterSettledRequest": {
      "requestDisposition": "commit",
      "sentinel": {
        "phase": "baseline",
        "disposition": "repair"
      },
      "reconnect": {
        "phase": "reconnect",
        "disposition": "repair"
      },
      "repairPending": true
    },
    "firstSentinelDuringRequest": {
      "sentinel": {
        "phase": "baseline",
        "disposition": "dirty"
      },
      "requestDisposition": "refetch"
    },
    "requestAfterFirstSentinel": {
      "sentinel": {
        "phase": "baseline",
        "disposition": "ignore"
      },
      "redundantRepairPending": false
    },
    "expiryDuringCommit": {
      "requestDisposition": "committed",
      "activeBeforeRender": false,
      "expiryAction": "repair",
      "repairPending": true
    },
    "cappedOverflow": true,
    "retainedAfterOverflow": [
      "tracked/new.md",
      "tracked/old.md"
    ],
    "liveBatches": {
      "eligibleUnseenFileUpsert": {
        "changed": true,
        "needsAuthoritativeRepair": true,
        "overflowed": true,
        "removedDescendants": 0,
        "retainedLowerBound": 2,
        "truncated": true,
        "retainedPaths": [
          "unseen/fresh.md",
          "page/new.md"
        ]
      },
      "ineligibleUnseenFileUpsert": {
        "changed": false,
        "needsAuthoritativeRepair": true,
        "overflowed": false,
        "removedDescendants": 0,
        "retainedLowerBound": 2,
        "truncated": true,
        "retainedPaths": [
          "page/new.md",
          "page/old.md"
        ]
      },
      "unknownRemove": {
        "changed": false,
        "needsAuthoritativeRepair": true,
        "overflowed": false,
        "removedDescendants": 0,
        "retainedLowerBound": 2,
        "truncated": true,
        "retainedPaths": [
          "page/new.md",
          "page/old.md"
        ]
      },
      "unseenFileToDirectory": {
        "changed": false,
        "needsAuthoritativeRepair": true,
        "overflowed": false,
        "removedDescendants": 0,
        "retainedLowerBound": 2,
        "truncated": true,
        "retainedPaths": [
          "page/new.md",
          "page/old.md"
        ]
      },
      "subtreeRemove": {
        "changed": true,
        "needsAuthoritativeRepair": true,
        "overflowed": false,
        "removedDescendants": 2,
        "retainedLowerBound": 1,
        "truncated": true,
        "retainedPaths": [
          "keep/visible.md"
        ]
      },
      "ordinaryDirectoryAggregate": {
        "changed": false,
        "needsAuthoritativeRepair": false,
        "overflowed": false,
        "removedDescendants": 0,
        "retainedLowerBound": null,
        "truncated": true,
        "retainedPaths": [
          "page/new.md",
          "page/old.md"
        ]
      },
      "ordinaryKnownWrite": {
        "changed": true,
        "needsAuthoritativeRepair": false,
        "overflowed": false,
        "removedDescendants": 0,
        "retainedLowerBound": null,
        "truncated": true,
        "retainedPaths": [
          "page/new.md",
          "page/old.md"
        ]
      },
      "knownRankRegression": {
        "changed": true,
        "needsAuthoritativeRepair": true,
        "overflowed": false,
        "removedDescendants": 0,
        "retainedLowerBound": 2,
        "truncated": true,
        "retainedPaths": [
          "page/new.md",
          "page/old.md"
        ]
      },
      "uncappedEligibleUpsert": {
        "changed": true,
        "needsAuthoritativeRepair": false,
        "overflowed": false,
        "removedDescendants": 0,
        "retainedLowerBound": null,
        "truncated": false,
        "retainedPaths": [
          "page/new.md",
          "unseen/fresh.md"
        ]
      },
      "knownRemoval": {
        "changed": true,
        "needsAuthoritativeRepair": true,
        "overflowed": false,
        "removedDescendants": 0,
        "retainedLowerBound": 1,
        "truncated": true,
        "retainedPaths": [
          "page/new.md"
        ]
      },
      "knownExpiry": {
        "changed": true,
        "needsAuthoritativeRepair": true,
        "overflowed": false,
        "removedDescendants": 0,
        "retainedLowerBound": 1,
        "truncated": true,
        "retainedPaths": [
          "page/new.md"
        ]
      }
    },
    "fixedWindowCoalescing": {
      "secondAction": "coalesced",
      "timerCount": 1,
      "repairs": [
        {
          "windowKey": "1h",
          "requestKey": "/api/recent?window=1h&limit=5000&types=.md",
          "preserveRows": true
        }
      ],
      "newerRequestAction": "dirty",
      "newerRequestDisposition": "refetch"
    },
    "failedRepairLifecycle": {
      "initialRepairDelay": 100,
      "firstFailure": "retrying",
      "firstRetryDelay": 500,
      "coalescedRetry": "coalesced",
      "timersAfterCoalescing": 1,
      "secondRetryDelay": 1000,
      "terminalFailure": "stale",
      "statusBeforeRecoverySignal": "stale",
      "pendingBeforeRecoverySignal": false,
      "recoverySignal": "repair",
      "recoverySignalDelay": 100,
      "statusAfterRecoverySignal": "retrying",
      "recoveryFailure": "retrying",
      "recoveryRetryDelay": 500,
      "statuses": [
        "retrying",
        "stale",
        "retrying"
      ]
    },
    "cancellation": {
      "pending": false,
      "status": "fresh",
      "lateFailure": "ignored",
      "statuses": [
        "retrying",
        "fresh"
      ]
    },
    "successReset": {
      "delayBeforeSuccess": 500,
      "statusAfterSuccess": "fresh",
      "delayAfterSuccess": 500,
      "status": "retrying",
      "statuses": [
        "retrying",
        "fresh",
        "retrying"
      ]
    },
    "integration": {
      "controlTransitions": {
        "enterRecent": "load-recent",
        "sameSelection": "apply",
        "sameWindowFilterChange": "refetch-recent",
        "returnToTree": "load-tree"
      },
      "cleanResponse": {
        "disposition": "committed",
        "activeDuringCommit": false,
        "activeDuringRender": false,
        "renderedPaths": [
          "alpha/a.md",
          "alpha/b.md",
          "bravo/a.md",
          "bravo/b.md",
          "charlie/a.md",
          "charlie/b.md"
        ],
        "request": "/api/recent?window=1h&limit=5000&types=.md",
        "trace": [
          "commit",
          "render"
        ]
      },
      "dirtyResponse": {
        "commitCalled": false,
        "disposition": "repair-scheduled",
        "repairPending": true
      },
      "staleSelectionResponse": {
        "commitCalled": false,
        "disposition": "ignored"
      },
      "failedBackgroundRepair": {
        "disposition": "repair-failed",
        "initialErrorShown": false,
        "repairDisposition": "repair",
        "retryPending": true,
        "status": "retrying"
      },
      "failedInitialLoad": {
        "disposition": "initial-failed",
        "initialErrorShown": true,
        "retryPending": false
      },
      "repairCallback": {
        "disposition": "repair",
        "fetches": [
          {
            "windowKey": "1h",
            "preserveRows": true
          }
        ],
        "staleDisposition": "cancelled"
      }
    }
  }
}
```

The catalog feed session pins connect-before-fetch ordering, buffered delta replay,
bounded snapshot commits, sentinel resynchronization, and retry without data loss.

```console
$ node tests/dom/catalog-feed-behavior.js
{
  "verified": [
    "no apply before start",
    "first start begins one fetch",
    "changes during fetch stay buffered",
    "bulk applies first",
    "bulk carries completeness",
    "buffered changes fold into the bulk in order",
    "small post-fetch changes use the direct point path",
    "fs.change uses the same scheduler-backed delivery seam",
    "sentinel before first fetch does nothing",
    "sentinel after a completed fetch refetches",
    "refetch folds changes buffered during it",
    "reconnect marks catalog coverage incomplete",
    "reconnect open refetches before its sentinel",
    "reconnect sentinel does not duplicate the open refetch",
    "completion after a partial reconnect payload refetches",
    "duplicate completion signals share one authoritative refetch",
    "partial reconnect does not claim completion before an authoritative payload",
    "completion refetch applies authoritative membership",
    "truncated completion repairs reconnect membership",
    "truncated completion never claims complete root coverage",
    "truncated completion refetch is authoritative but incomplete",
    "reconnect discards an unfinished initial response",
    "reconnect queues a replacement for the initial fetch",
    "replacement initial fetch applies",
    "304 reconnect restores known complete coverage",
    "304 reconnect keeps capped coverage incomplete",
    "resync refetches",
    "changes during resync refetch fold into its commit",
    "failure schedules a retry",
    "nothing applied on failure",
    "retry folds the delta buffered across the failure into its bulk",
    "stale pre-resync response is never applied",
    "resync during a fetch still queues a follow-up fetch",
    "follow-up fetch applies the new root's catalog",
    "first sentinel refetches",
    "response overtaken by a second sentinel is discarded",
    "sentinel during a fetch queues a follow-up",
    "queued follow-up applies",
    "index completion marks the catalog",
    "disposed feed applies nothing",
    "progress poll function is extractable",
    "failed progress does not complete the catalog",
    "capped progress repairs without claiming complete coverage",
    "truncated bulk applies its files",
    "a truncated catalog is not reported complete",
    "a truncated terminal event does not mark the catalog complete",
    "a large steady change is staged",
    "walk completion issues the authoritative refetch",
    "a change after the refetch began survives its older authoritative payload"
  ]
}
```

The catalog ordering session feeds the exact production modules with a valid
UTF-8-ordered payload whose BMP private-use paths precede its astral paths.
It pins the browser’s complete UTF-16-ordered projection and runs the larger 200,000-row
responsiveness gate through the focused pytest wrapper.

```console
$ node tests/dom/catalog-unicode-order-session.js
{
  "browserOrder": [
    "astral",
    "bmp-private-use"
  ],
  "complete": true,
  "files": 40000,
  "providerOrder": [
    "bmp-private-use",
    "astral"
  ],
  "sliced": true,
  "workItemLimit": 4096
}
```

The large catalog session applies the production 300,000-row shape through the exact
bounded scheduler. It pins the one-pass initial projection and attributes every bulk,
catalog-delta, and filesystem-delta delivery callback without requiring a live delta
from a settled server.

```console
$ node tests/dom/catalog-feed-large-session.js
{
  "attributedDeliveryLabels": [
    "apiCatalog:parse",
    "knownFileCatalog:applyBulkSnapshot",
    "knownFileCatalog:applyCatalogChange",
    "knownFileCatalog:applyEventChange"
  ],
  "catalogRows": 300000,
  "initialBulkWorkItems": 300003,
  "initialFetches": 1,
  "sliceItemLimit": 4096
}
```

The navigation route session pins the canonical file and comparison identities used by
history updates, including segment encoding, fragments, Windows-native identities, and
invalid path rejection.

```console
$ node tests/dom/navigation-route-behavior.js
{
  "verified": [
    "slash-bearing Git ref gets one encoded revision segment",
    "slash-bearing Git ref parses",
    "slash-bearing Git ref and inner path parse independently",
    "reject encoded separator in commit inner path /commit/main/src%2Fapp.py",
    "reject encoded separator in commit inner path /commit/main/src%5Capp.py",
    "reject encoded separator in commit inner path /commit/main/src%00app.py",
    "reject invalid commit revision \"\"",
    "reject invalid commit revision \".bad\"",
    "reject invalid commit revision \"bad ref\"",
    "reject invalid commit revision \"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\"",
    "root href",
    "folder href keeps its slash",
    "path segments encode independently",
    "query and fragment stay outside path identity",
    "parse root",
    "parse folder",
    "parse encoded path once",
    "query escapes remain data rather than delimiters",
    "reserved keys are carried, not yet interpreted",
    "a query round-trips losslessly through parse and href",
    "stripping reserved keys yields the canonical content URL",
    "percent-looking data is not decoded twice",
    "native URL for 100%25.md",
    "identity from /view/100%25.md",
    "native URL for report%2520final.txt",
    "identity from /view/report%2520final.txt",
    "native URL for d%251/雪.md",
    "identity from /view/d%251/%E9%9B%AA.md",
    "native URL for bad%FF 雪%25.txt",
    "identity from /view/bad%FF%20%E9%9B%AA%25.txt",
    "display percent-looking filename literally",
    "Windows native URL for lone%D8%00.txt",
    "Windows identity from /view/lone%ED%A0%80.txt",
    "Windows native URL for lone%DF%FF.txt",
    "Windows identity from /view/lone%ED%BF%BF.txt",
    "Windows native URL for lone%D8%80.txt",
    "Windows identity from /view/lone%ED%A2%80.txt",
    "Windows native URL for unicode؀.txt",
    "Windows identity from /view/unicode%D8%80.txt",
    "reject unrelated route",
    "reject missing canonical root slash",
    "reject malformed escape",
    "reject encoded slash",
    "reject encoded backslash",
    "reject literal backslash",
    "reject literal parent traversal",
    "reject encoded parent traversal",
    "reject encoded NUL",
    "reject empty interior segment",
    "format rejects leading slash",
    "format rejects dot segment",
    "format rejects parent segment",
    "format rejects backslash",
    "format rejects NUL",
    "public href uses the canonical codec",
    "startup applies pathname route",
    "startup does not rewrite history",
    "public current reads controller state",
    "user navigation pushes",
    "path navigation reports a fetch boundary",
    "latest navigation context is current",
    "folder slash canonicalization replaces",
    "canonical folder is current",
    "same-file fragment gets a real URL",
    "same-file fragment avoids a fetch boundary",
    "superseded navigation context is stale",
    "popstate restores from location",
    "back to landing clears target",
    "landing callback receives null",
    "dispose removes popstate",
    "a hash alone selects no file",
    "a hash-only landing applies no target"
  ]
}
```

The asset loader session pins lazy construction, dependency order, concurrent request
coalescing, partial-failure recovery, and validation of promised globals.

```console
$ node tests/dom/asset-loader-behavior.js
{"appendedBeforeAnyRequest":0,"orderedLoad":["chart.js","plugin.js","adapter.js"],"notifiedPerScript":["chart.js","plugin.js","adapter.js"],"loadedFlag":true,"appendsOnSecondRequest":0,"skippedUngatedDependency":["chart.js"],"appendsWhileThreeCallersWait":1,"appendsAfterSharedLoadSettled":1,"unknownBundle":"Unknown asset bundle: absent","failedScript":"Failed to load asset: chart.js","loadedFlagAfterFailure":false,"appendsAfterFailedRetry":2,"partialFailureRetryAppends":["chart.js","charts-runtime.js","adapter.js","adapter.js"],"partialFailureNotifications":["chart.js","charts-runtime.js","adapter.js"],"partialFailureLoaded":true,"missingProvidedGlobal":"Asset chart.js did not provide expected global: Chart","missingProvidedGlobalFirstAppends":["chart.js"],"missingProvidedGlobalFirstNotifications":[],"missingProvidedGlobalLatched":false,"missingProvidedGlobalRetryAppends":["chart.js","chart.js","plugin.js"],"missingProvidedGlobalRetryNotifications":["chart.js","plugin.js"],"missingProvidedGlobalRetryLoaded":true,"concurrentStrongFailure":"Asset shared.js did not provide expected global: Shared","concurrentStrongRetryAppends":["shared.js","shared.js"],"concurrentStrongRetryLoaded":true}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
