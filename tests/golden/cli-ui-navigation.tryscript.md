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

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
