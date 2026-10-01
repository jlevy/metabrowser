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
Each checkpoint records what the production feed had done by then: how many fetches it
had begun, and what it had delivered to the catalog since the checkpoint before.

```console
$ node tests/dom/catalog-feed-behavior.js
{
  "observed": {
    "no apply before start": {"fetches":0,"delivered":[]},
    "first start begins one fetch": {"fetches":1,"delivered":[]},
    "changes during fetch stay buffered": {"fetches":1,"delivered":[]},
    "bulk applies first": {"fetches":1,"delivered":[{"kind":"bulk","files":[{"p":"bulk.txt","e":".txt"}],"coverage":"complete","authoritative":true,"buffered":[{"upserts":[{"p":"early.txt","e":".txt"}],"removes":[]},{"upserts":[{"p":"during.txt","e":".txt"}],"removes":[]}]}]},
    "bulk carries completeness": {"fetches":1,"delivered":[]},
    "buffered changes fold into the bulk in order": {"fetches":1,"delivered":[]},
    "small post-fetch changes use the direct point path": {"fetches":1,"delivered":[{"kind":"change","payload":{"non_file_paths":["replaced-link"],"upserts":[{"p":"live.txt","e":".txt"}],"removes":[]}}]},
    "fs.change uses the same scheduler-backed delivery seam": {"fetches":1,"delivered":[{"kind":"event-change","ops":[{"op":"remove","path":"old-dir"}]}]},
    "sentinel before first fetch does nothing": {"fetches":0,"delivered":[]},
    "sentinel after a completed fetch refetches": {"fetches":2,"delivered":[{"kind":"bulk","files":[],"coverage":"complete","authoritative":true,"buffered":[]},{"kind":"markIncomplete"}]},
    "refetch folds changes buffered during it": {"fetches":2,"delivered":[{"kind":"bulk","files":[],"coverage":"complete","authoritative":true,"buffered":[{"upserts":[{"p":"gap.txt","e":".txt"}],"removes":[]}]}]},
    "reconnect marks catalog coverage incomplete": {"fetches":2,"delivered":[{"kind":"bulk","files":[{"p":"deleted-while-away.txt","e":".txt"}],"coverage":"complete","authoritative":true,"buffered":[]},{"kind":"markIncomplete"}]},
    "reconnect open refetches before its sentinel": {"fetches":2,"delivered":[]},
    "reconnect sentinel does not duplicate the open refetch": {"fetches":2,"delivered":[]},
    "completion after a partial reconnect payload refetches": {"fetches":3,"delivered":[{"kind":"bulk","files":[],"coverage":"partial","authoritative":false,"buffered":[]}]},
    "duplicate completion signals share one authoritative refetch": {"fetches":3,"delivered":[]},
    "partial reconnect does not claim completion before an authoritative payload": {"fetches":3,"delivered":[]},
    "completion refetch applies authoritative membership": {"fetches":3,"delivered":[{"kind":"bulk","files":[],"coverage":"complete","authoritative":true,"buffered":[]}]},
    "truncated completion repairs reconnect membership": {"fetches":3,"delivered":[{"kind":"bulk","files":[{"p":"deleted-while-away.txt","e":".txt"}],"coverage":"complete","authoritative":true,"buffered":[]},{"kind":"markIncomplete"},{"kind":"bulk","files":[],"coverage":"partial","authoritative":false,"buffered":[]}]},
    "truncated completion never claims complete root coverage": {"fetches":3,"delivered":[]},
    "truncated completion refetch is authoritative but incomplete": {"fetches":3,"delivered":[{"kind":"bulk","files":[],"coverage":"truncated","authoritative":true,"buffered":[]}]},
    "reconnect discards an unfinished initial response": {"fetches":2,"delivered":[{"kind":"markIncomplete"}]},
    "reconnect queues a replacement for the initial fetch": {"fetches":2,"delivered":[]},
    "replacement initial fetch applies": {"fetches":2,"delivered":[{"kind":"bulk","files":[{"p":"after-reconnect.txt","e":".txt"}],"coverage":"complete","authoritative":true,"buffered":[]}]},
    "304 reconnect restores known complete coverage": {"fetches":2,"delivered":[{"kind":"bulk","files":[],"coverage":"complete","authoritative":true,"buffered":[]},{"kind":"markIncomplete"},{"kind":"bulk","files":[],"coverage":"complete","authoritative":false,"buffered":[]}]},
    "304 reconnect keeps capped coverage incomplete": {"fetches":2,"delivered":[{"kind":"bulk","files":[],"coverage":"truncated","authoritative":true,"buffered":[]},{"kind":"markIncomplete"},{"kind":"bulk","files":[],"coverage":"truncated","authoritative":false,"buffered":[]}]},
    "304 reconnect restores known truncated coverage": {"fetches":2,"delivered":[]},
    "resync refetches": {"fetches":2,"delivered":[{"kind":"bulk","files":[],"coverage":"complete","authoritative":true,"buffered":[]},{"kind":"markIncomplete"}]},
    "changes during resync refetch fold into its commit": {"fetches":2,"delivered":[{"kind":"bulk","files":[],"coverage":"partial","authoritative":false,"buffered":[{"upserts":[{"p":"afterswap.txt","e":".txt"}],"removes":[]}]}]},
    "failure schedules a retry": {"fetches":1,"delivered":[]},
    "nothing applied on failure": {"fetches":1,"delivered":[]},
    "retry folds the delta buffered across the failure into its bulk": {"fetches":2,"delivered":[{"kind":"bulk","files":[{"p":"bulk.txt","e":".txt"}],"coverage":"complete","authoritative":true,"buffered":[{"upserts":[{"p":"kept.txt","e":".txt"}],"removes":[]}]}]},
    "stale pre-resync response is never applied": {"fetches":2,"delivered":[{"kind":"markIncomplete"}]},
    "resync during a fetch still queues a follow-up fetch": {"fetches":2,"delivered":[]},
    "follow-up fetch applies the new root's catalog": {"fetches":2,"delivered":[{"kind":"bulk","files":[{"p":"new-root.txt","e":".txt"}],"coverage":"complete","authoritative":true,"buffered":[]}]},
    "first sentinel refetches": {"fetches":2,"delivered":[{"kind":"bulk","files":[],"coverage":"complete","authoritative":true,"buffered":[]},{"kind":"markIncomplete"}]},
    "response overtaken by a second sentinel is discarded": {"fetches":3,"delivered":[{"kind":"markIncomplete"}]},
    "sentinel during a fetch queues a follow-up": {"fetches":3,"delivered":[]},
    "queued follow-up applies": {"fetches":3,"delivered":[{"kind":"bulk","files":[{"p":"post-drop.txt","e":".txt"}],"coverage":"complete","authoritative":true,"buffered":[]}]},
    "index completion marks the catalog": {"fetches":0,"delivered":[{"kind":"markComplete"}]},
    "disposed feed applies nothing": {"fetches":1,"delivered":[]},
    "progress poll function is extractable": {"refreshIndexProgress":"string"},
    "failed progress does not complete the catalog": {"onIndexComplete":[]},
    "capped progress repairs without claiming complete coverage": {"onIndexComplete":[true]},
    "truncated bulk applies its files": {"fetches":1,"delivered":[{"kind":"bulk","files":[{"p":"capped.txt","e":".txt"}],"coverage":"truncated","authoritative":true,"buffered":[]}]},
    "a truncated catalog is not reported complete": {"fetches":1,"delivered":[]},
    "a truncated terminal event does not mark the catalog complete": {"fetches":1,"delivered":[{"kind":"markTruncated"}]},
    "a truncated terminal event marks the catalog truncated": {"fetches":1,"delivered":[{"kind":"bulk","files":[{"p":"early.txt","e":".txt"}],"coverage":"partial","authoritative":false,"buffered":[]},{"kind":"markTruncated"}]},
    "a large steady change is staged": {"yields":1},
    "walk completion issues the authoritative refetch": {"fetches":3},
    "a change after the refetch began survives its older authoritative payload": {"complete":true,"files":5301,"hasNew":true}
  }
}
? 0
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
Each line is what the production module answered: an address, a parsed target, a history
decision, or the error a refused call threw.

```console
$ node tests/dom/navigation-route-behavior.js
{
  "observed": {
    "slash-bearing Git ref gets one encoded revision segment": "/commit/refs%2Fheads%2Fmain",
    "slash-bearing Git ref parses": {"revision":"refs/heads/main","file":""},
    "slash-bearing Git ref and inner path parse independently": {"revision":"refs/heads/feature","file":"src/app.py"},
    "reject encoded separator in commit inner path /commit/main/src%2Fapp.py": null,
    "reject encoded separator in commit inner path /commit/main/src%5Capp.py": null,
    "reject encoded separator in commit inner path /commit/main/src%00app.py": null,
    "reject an empty commit revision": "TypeError: commit route requires a valid revision",
    "reject a dot-leading commit revision": "TypeError: commit route requires a valid revision",
    "reject a spaced commit revision": "TypeError: commit route requires a valid revision",
    "reject an over-long commit revision": "TypeError: commit route requires a valid revision",
    "pull-request page href": "/pull/7",
    "pull-request Files changed href": "/pull/7/files",
    "pull-request page parses": {"number":7,"tab":""},
    "pull-request tab parses with a trailing slash": {"number":7,"tab":"files"},
    "reject pull-request route /pull/0": null,
    "reject pull-request route /pull/07": null,
    "reject pull-request route /pull/7/commits": null,
    "reject pull-request route /pull/7/files/x": null,
    "reject pull-request route /pull/x": null,
    "reject invalid pull-request href 0/": "TypeError: pull route requires a pull-request number and a known tab",
    "reject invalid pull-request href 7/commits": "TypeError: pull route requires a pull-request number and a known tab",
    "back between a page's tabs switches the tab": {"action":"tab","tab":"files"},
    "back onto a page whose pane a commit took mounts it": {"action":"mount","number":7,"tab":""},
    "back onto another pull request's page mounts it": {"action":"mount","number":7,"tab":"files"},
    "back from a file view is the controller's": null,
    "back onto a view route is not a page's": null,
    "root href": "/view/",
    "folder href keeps its slash": "/view/docs/",
    "path segments encode independently": "/view/docs/a%20b/%25%20notes/%E9%9B%AA.md",
    "query and fragment stay outside path identity": "/view/docs/a.md?plain=1&x=a%20b#A%2FB%20%231",
    "parse root": {"path":""},
    "parse folder": {"path":"docs/"},
    "parse encoded path once": {"path":"a b/%25 notes/雪.md","query":"plain=1&x=a%20b","fragment":"A/B #1"},
    "query escapes remain data rather than delimiters": "/view/docs/a.md?value=a%26b&literal=%25",
    "reserved keys are carried, not yet interpreted": {"path":"docs/a.md","query":"_mb_view=source&plain=1"},
    "a query round-trips losslessly through parse and href": "/view/docs/a.md?_mb_view=source&plain=1#setup",
    "stripping reserved keys yields the canonical content URL": "/view/docs/a.md",
    "percent-looking data is not decoded twice": {"path":"docs/a%252Fb.md"},
    "native URL for 100%25.md": "/view/100%25.md",
    "identity from /view/100%25.md": {"path":"100%25.md"},
    "native URL for report%2520final.txt": "/view/report%2520final.txt",
    "identity from /view/report%2520final.txt": {"path":"report%2520final.txt"},
    "native URL for d%251/雪.md": "/view/d%251/%E9%9B%AA.md",
    "identity from /view/d%251/%E9%9B%AA.md": {"path":"d%251/雪.md"},
    "native URL for bad%FF 雪%25.txt": "/view/bad%FF%20%E9%9B%AA%25.txt",
    "identity from /view/bad%FF%20%E9%9B%AA%25.txt": {"path":"bad%FF 雪%25.txt"},
    "native URL for a%5Cb.txt": "/view/a%5Cb.txt",
    "identity from /view/a%5Cb.txt": {"path":"a%5Cb.txt"},
    "native URL for %255C.md": "/view/%255C.md",
    "identity from /view/%255C.md": {"path":"%255C.md"},
    "display percent-looking filename literally": "a%20%.txt",
    "display a POSIX backslash name and a literal %5C": "a\\b/%5C.md",
    "display GitPath README wire": "README.md",
    "display GitPath nested wire": "docs/note.txt",
    "display GitPath percent name": "100%.html",
    "display GitPath nested percent name": "docs/100%.md",
    "display GitPath one crumb of a wire": "note.txt",
    "display GitPath patch container inner": "change.patch/src/app.py",
    "display mixed filesystem path is not a GitPath wire": "docs/g1-UkVBRE1FLm1k",
    "display filesystem g1-looking filename literally": "g1-UkVBRE1FLm1k",
    "GitPath wire of README.md displays as it": "README.md",
    "GitPath wire of docs/note.txt displays as it": "docs/note.txt",
    "GitPath wire of 100%.html displays as it": "100%.html",
    "GitPath wire of docs/雪.md displays as it": "docs/雪.md",
    "GitPath wire of a b/c?#.txt displays as it": "a b/c?#.txt",
    "GitPath wire is one token per segment": "g1-c3Jj/g1-YXBwLnB5",
    "GitPath wire is unpadded base64url": "g1-YT8-",
    "GitPath wire of a name that is not UTF-8 is its bytes": "g1-ZOk/g1-Zg",
    "an empty path has no GitPath wire": null,
    "a leading slash has no GitPath wire": null,
    "a trailing slash has no GitPath wire": null,
    "an empty segment has no GitPath wire": null,
    "no bytes has no GitPath wire": null,
    "display filesystem g1-looking filename with explicit kind": "g1-UkVBRE1FLm1k",
    "display invalid GitPath atom stays a wire token": "g1-!!!",
    "display GitPath newline name replaces C0": "new�line.txt",
    "display GitPath invalid UTF-8 name": "x�.txt",
    "display a decoded Git name again is not idempotent": "u�Z",
    "Windows native URL for lone%D8%00.txt": "/view/lone%ED%A0%80.txt",
    "Windows identity from /view/lone%ED%A0%80.txt": {"path":"lone%D8%00.txt"},
    "Windows native URL for lone%DF%FF.txt": "/view/lone%ED%BF%BF.txt",
    "Windows identity from /view/lone%ED%BF%BF.txt": {"path":"lone%DF%FF.txt"},
    "Windows native URL for lone%D8%80.txt": "/view/lone%ED%A2%80.txt",
    "Windows identity from /view/lone%ED%A2%80.txt": {"path":"lone%D8%80.txt"},
    "Windows native URL for unicode؀.txt": "/view/unicode%D8%80.txt",
    "Windows identity from /view/unicode%D8%80.txt": {"path":"unicode؀.txt"},
    "Windows rejects an encoded backslash": null,
    "a pin refuses an encoded backslash in a container inner": null,
    "reject unrelated route": null,
    "reject missing canonical root slash": null,
    "reject malformed escape": null,
    "reject encoded slash": null,
    "reject literal backslash": null,
    "reject literal parent traversal": null,
    "reject encoded parent traversal": null,
    "reject encoded NUL": null,
    "reject empty interior segment": null,
    "format rejects leading slash": "TypeError: navigation path must be a safe served-root-relative path",
    "format rejects dot segment": "TypeError: navigation path must already be normalized",
    "format rejects parent segment": "TypeError: navigation path must already be normalized",
    "format rejects backslash": "TypeError: navigation path must be a safe served-root-relative path",
    "format rejects NUL": "TypeError: navigation path must be a safe served-root-relative path",
    "a page is not shown while it mounts": null,
    "a mounted page opens": {"status":"opened"},
    "the mounted page is shown": 7,
    "a tab link opens the tab": {"status":"opened"},
    "the shown page's route opens without a push": {"status":"opened"},
    "a landing the controller applies is left to it": null,
    "a tab keeps the page and puts the tab in the URL": ["claim 1 (pull-request)","mount /pull/7","push /pull/7/files","#7 tab \"files\"","#7 tab \"files\"","#7 tab \"\""],
    "the served pull request's page opens": {"status":"opened"},
    "the served pull request's page replaces the other": ["claim 1 (pull-request)","mount /pull/8/files","push /pull/7/files","#8 disposed","claim 2 (pull-request)","mount /pull/7/files"],
    "the served pull request is shown": 7,
    "a page a later route superseded is cancelled": {"status":"cancelled"},
    "a page a file claim superseded is cancelled": {"status":"cancelled"},
    "a superseded page is never shown": null,
    "superseded pages are disposed as they arrive": ["claim 1 (pull-request)","mount /pull/7","claim 2 (pull-request)","mount /pull/7/files","#7 disposed","claim 3 (file)","#7 disposed"],
    "a page another claim replaced is not shown": null,
    "back onto a replaced page mounts it": {"action":"mount","number":7,"tab":""},
    "no plugin leaves no page shown": null,
    "a replaced or unmounted page mounts again": ["claim 1 (pull-request)","mount /pull/7","#7 disposed","claim 2 (commit)","claim 3 (pull-request)","mount /pull/7","claim 4 (pull-request)","mount /pull/7"],
    "public href uses the canonical codec": "/view/public%20path.md#part",
    "startup applies pathname route": {"path":"docs/start.md","query":"plain=1","fragment":"intro"},
    "startup does not rewrite history": [],
    "public current reads controller state": {"path":"docs/start.md","query":"plain=1","fragment":"intro"},
    "user navigation pushes": ["push","/view/docs/next.md"],
    "path navigation reports a fetch boundary": true,
    "latest navigation context is current": true,
    "folder slash canonicalization replaces": ["replace","/view/docs/next.md/"],
    "canonical folder is current": {"path":"docs/next.md/"},
    "same-file fragment gets a real URL": ["push","/view/docs/next.md/#details"],
    "same-file fragment avoids a fetch boundary": false,
    "superseded navigation context is stale": false,
    "popstate restores from location": {"path":"back.md","fragment":"old"},
    "back to landing clears target": null,
    "landing callback receives null": null,
    "dispose removes popstate": [],
    "a hash alone selects no file": null,
    "a hash-only landing applies no target": [null]
  }
}
? 0
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
