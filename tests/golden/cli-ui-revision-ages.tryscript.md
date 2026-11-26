---
cwd: ../..
sandbox: false
---
# Golden Test: A Revision’s Page While Its File Ages Are Read

A Git revision’s files get their ages from `git last-modified`, which the server runs in
the background and never makes a page wait for.
A tree, a grouped tree, or a Recent list asked for before the answer lands says
`ages.state: "dating"` and has every file undated.
`static/revision-ages.js` watches for that state and asks `/api/index/progress`, which
carries the same state, until it changes; then it asks the shell to draw once more, so
the rows that had no age get one without the reader doing anything.

This browserless session runs the real module under fake timers and a scripted progress
route, three ways: through the controller, through `mount`, the glue the page runs, and
through the page itself, where the functions of `app.js` that the module meets are
lifted out of it and run against the module as the asset loader would bring it.
The transcript pins these behaviors:

- A response with no `ages`, or one that says the answer is in (`ready`, `partial`,
  `unavailable`), starts no watch and holds no timer.
- A response that says `dating` starts one watch; seeing `dating` again while it runs
  adds no second timer.
  The watch asks at the pace the page’s settings name.
- While the answer is `dating` the watch keeps asking.
  When it lands, `ready`, `partial` or `failed`, the shell is asked to draw once with
  the state, and the watch holds nothing.
- A poll that fails is asked again, three times in a row, and the first answer it then
  gets lands; a fourth failure ends the watch without drawing.
- A response that says the answer landed while the watch runs is the landing, as it may
  be the root’s alone; one with no watch running draws nothing.
- A watch gives up once it has run past the bound the page’s settings name, which the
  server derives from its own bound on a read.
- The line that counts the files a filter keeps says what the state is when it is not
  all dated: that the ages are being read, why they could not be read, or how many files
  could not be dated. It is one more item of a line that is already there, so it moves
  nothing, and it is added whichever comes first, the line or the state; drawn again, it
  holds one clause, not two.
- On the page, a response that says `dating` asks the asset loader for the module once,
  shows “…” for the Modified within counts and the pending line, and a landed answer
  draws the tree, the Recent list and the open file again once, with the counts and no
  clause. A whole answer asks for nothing; a menu that is open has its counts patched,
  not rebuilt.
- A revision’s Recent list names its folders by the names the server sends beside each
  row’s path (`dir_names`), because a path there is a wire whose segments are encoded; a
  folder’s own rows are named by their path.

```console
$ node tests/dom/revision-ages-session.js
{
  "a response with no ages is not about file ages": {
    "watching": false,
    "timers": 0,
    "progressRequests": 0,
    "landed": []
  },
  "an answer that has landed starts no watch": {
    "watching": false,
    "timers": 0,
    "progressRequests": 0,
    "landed": []
  },
  "dating starts one watch that polls until the answer lands, then draws once": {
    "observed": {
      "watching": true,
      "timers": 1,
      "progressRequests": 0,
      "landed": [],
      "delays": [
        500
      ]
    },
    "observedAgain": {
      "watching": true,
      "timers": 1,
      "progressRequests": 0,
      "landed": [],
      "delays": [
        500
      ]
    },
    "firstPoll": {
      "watching": true,
      "timers": 1,
      "progressRequests": 1,
      "landed": []
    },
    "secondPoll": {
      "watching": true,
      "timers": 1,
      "progressRequests": 2,
      "landed": []
    },
    "landed": {
      "watching": false,
      "timers": 0,
      "progressRequests": 3,
      "landed": [
        "landed {\"state\":\"ready\",\"dated\":7}"
      ]
    }
  },
  "a partial answer is an answer: it draws once and stops": {
    "watching": false,
    "timers": 0,
    "progressRequests": 1,
    "landed": [
      "landed {\"state\":\"partial\",\"dated\":3,\"older_than\":1700000000}"
    ]
  },
  "a failed read is an answer too: the page is told, and asks no more": {
    "watching": false,
    "timers": 0,
    "progressRequests": 1,
    "landed": [
      "landed {\"state\":\"failed\",\"reason\":\"git_failed\"}"
    ]
  },
  "a poll that fails is asked again, and the answer it then gets lands": {
    "firstFailure": {
      "watching": true,
      "timers": 1,
      "progressRequests": 1,
      "landed": []
    },
    "secondFailure": {
      "watching": true,
      "timers": 1,
      "progressRequests": 2,
      "landed": []
    },
    "landed": {
      "watching": false,
      "timers": 0,
      "progressRequests": 3,
      "landed": [
        "landed {\"state\":\"ready\"}"
      ]
    }
  },
  "a poll that keeps failing ends the watch without drawing": {
    "first": {
      "watching": true,
      "timers": 1,
      "progressRequests": 1,
      "landed": []
    },
    "second": {
      "watching": true,
      "timers": 1,
      "progressRequests": 2,
      "landed": []
    },
    "third": {
      "watching": true,
      "timers": 1,
      "progressRequests": 3,
      "landed": []
    },
    "gaveUp": {
      "watching": false,
      "timers": 0,
      "progressRequests": 4,
      "landed": []
    }
  },
  "a response that says the answer landed while the watch runs is the landing": {
    "watching": false,
    "timers": 0,
    "progressRequests": 0,
    "landed": [
      "landed {\"state\":\"ready\"}"
    ]
  },
  "a response that says it landed with no watch running draws nothing": {
    "watching": false,
    "timers": 0,
    "progressRequests": 0,
    "landed": []
  },
  "a watch that outlasts the bound the settings give it gives up": {
    "insideTheBound": {
      "watching": true,
      "timers": 1,
      "progressRequests": 1,
      "landed": []
    },
    "pastTheBound": {
      "watching": false,
      "timers": 0,
      "progressRequests": 2,
      "landed": []
    }
  },
  "the page's glue asks the progress route at the settings' pace": {
    "delays": [
      250,
      250
    ],
    "asked": [
      {
        "url": "/api/index/progress",
        "options": {
          "cache": "no-store"
        }
      },
      {
        "url": "/api/index/progress",
        "options": {
          "cache": "no-store"
        }
      }
    ],
    "landed": [
      {
        "state": "partial",
        "dated": 2
      }
    ],
    "watching": false
  },
  "what the filtered count says of each state": {
    "absent": null,
    "ready": null,
    "dating": "Reading file ages…",
    "failedGit": "Git could not read this revision's file ages. Files show no age.",
    "failedTooMany": "This revision has too many files to date. Files show no age.",
    "failedUnknown": "File ages could not be read. Files show no age.",
    "partialShallow": "37 files are older than 2023-11-14.",
    "partialCut": "10 files are older than 2023-11-14.",
    "partialOne": "1 file could not be dated.",
    "partialFilteredList": "7 files could not be dated.",
    "partialNoneInTheList": null
  },
  "the page's own functions meet the module": {
    "aWholeAnswerAsksForNothing": {
      "events": [],
      "counts": [
        0,
        0
      ]
    },
    "aResponseWithNoAgesAsksForNothing": {
      "events": [],
      "timers": 0
    },
    "theFirstResponseSaysDatingWithNoFilterSet": {
      "events": [
        "renderNavFilterBar",
        "ensureAsset revision-ages"
      ],
      "menuCounts": [
        "…",
        "…"
      ],
      "tallyLine": [],
      "timers": 1
    },
    "theShellDrawsTheFilteredLine": {
      "tallyLine": [
        "Reading file ages…"
      ]
    },
    "theAnswerLands": {
      "events": [
        "fetch /api/index/progress",
        "event metabrowser:file-ages-landed {\"state\":\"ready\",\"files\":6,\"dated\":6}",
        "subtreeCache.clear",
        "fileCache.clear",
        "loadTree {\"reconcileMountedRoot\":true}",
        "loadRecent",
        "selectFile docs/guide.md in rendered"
      ]
    },
    "theRedrawnTreeSaysReady": {
      "events": [
        "renderNavFilterBar"
      ],
      "menuCounts": [
        2,
        5
      ],
      "tallyLine": [],
      "timers": 0
    },
    "aFailedReadIsSaid": {
      "events": [
        "ensureAsset revision-ages"
      ],
      "tallyLine": [
        "Git could not read this revision's file ages. Files show no age."
      ],
      "timers": 0
    },
    "aShallowHistoryIsSaid": {
      "tallyLine": [
        "37 files are older than 2023-11-14."
      ],
      "timers": 0
    },
    "theLineIsDrawnAgainWithOneClause": {
      "tallyLine": [
        "37 files are older than 2023-11-14."
      ]
    },
    "theRecentListSaysWhyItIsEmpty": {
      "whole": "<div class=\"recent-empty\">No files were modified during the selected time range.</div>",
      "dating": "<div class=\"recent-empty\">Reading file ages…</div>",
      "failed": "<div class=\"recent-empty\">No file ages to filter by.</div>",
      "ready": "<div class=\"recent-empty\">No files were modified during the selected time range.</div>"
    },
    "anOpenMenuOnlyHasItsCountsPatched": {
      "events": [
        "patchOpenRecencyTallyCounts",
        "ensureAsset revision-ages"
      ]
    },
    "aRereadKeepsWhatThePaneShows": {
      "aFileInSource": [
        "subtreeCache.clear",
        "fileCache.clear",
        "loadTree {\"reconcileMountedRoot\":true}",
        "loadRecent",
        "selectFile docs/guide.md in source"
      ],
      "aFolderInTreemap": [
        "subtreeCache.clear",
        "fileCache.clear",
        "loadTree {\"reconcileMountedRoot\":true}",
        "loadRecent",
        "selectFile docs in treemap"
      ],
      "aPullRequestPage": [
        "subtreeCache.clear",
        "fileCache.clear",
        "loadTree {\"reconcileMountedRoot\":true}",
        "loadRecent"
      ],
      "nothingChosen": [
        "subtreeCache.clear",
        "fileCache.clear",
        "loadTree {\"reconcileMountedRoot\":true}",
        "loadRecent"
      ]
    }
  },
  "a revision's Recent list names its folders by their names": {
    "withDirNames": [
      {
        "name": "doc",
        "path": "g1-ZG9j"
      }
    ],
    "aFoldersOwnRows": [
      {
        "name": "doc",
        "path": "doc"
      }
    ]
  }
}
? 0
```
