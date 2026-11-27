---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Pull Request’s Readiness in the Pulls Tab and on Stacks

An open pull request’s row in the Pulls tab has a readiness column on its last line,
between its change line and its age: the verdict’s glyph in its tone, and its label
after it where the list is wide enough (mb-3n21). A stack’s member row, in the stack
menu and on the stack’s page, ends with the same glyph.
The server judges each pull request (`GET pull-statuses`), from the status the scan of
every open pull request kept, which the list’s own ask starts (`POST pulls-refresh`),
for the head and the lifecycle the catalog names.
This browserless session runs the production code that decides which rows are read and
what each draws, `builtin_plugins/github/row-readiness.js`, and that draws it,
`builtin_plugins/github/stack-member-row.js`, on the server’s own answers, which
`tests/test_github_pulls_readiness_session.py` records: before the scan, while it runs,
once it has ended, after a push it has not read, after a scan another tab’s Refresh
started, and after a pull request is marked a draft.
The session prints in two parts, each a command of its own, since one would be larger
than the matcher compiles.

`lane` drives the lane alone, with the browser’s idle time and its clock in the
session’s hands.
Each step’s `draws` is what each row draws, as a surface’s paint asks it
before the surface asks for any row: the verdict, its tone, and its label, or `none`.
`asked` is what the step read, the rows drawn in one request when the browser is idle,
`repainted` the rows the lane drew again, and `lane` the lane’s own state.
A closed or merged row is never asked, and draws none.
A row’s answer holds until the list’s ask says the scan started; until the ask or a read
says a scan ended later than any the document had heard of, whoever started it, here
another tab’s Refresh, as a look at the mirror’s base branches starts one after an ask;
until a pull request page reads a newer status of its own; until the row’s head or state
moves; or, on a stack’s member rows, which no ask reaches, until it is a minute old.
A Pulls tab mounted again draws each glyph in its first paint, from the document’s
index. A verdict is drawn for the head and the state it judged only, so a pushed row
draws none until the server judges the new head, and a row marked a draft none until it
judges the draft, even while a read fails; a read that fails keeps each glyph and is
asked again a minute on; and a server with no GitHub repository answers once for every
row.

```console
$ node tests/dom/github-pulls-readiness-session.js
{
  "lane": [
    {
      "step": "the list draws six rows: nothing is read until the browser is idle",
      "draws": {
        "#106": "none",
        "#105": "none",
        "#10": "none",
        "#9": "none",
        "#8": "none",
        "#7": "none"
      },
      "asked": [],
      "lane": {
        "wanted": [
          106,
          105,
          10,
          7
        ],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "idle: one read names the four open rows, and none of the merged or closed ones; no scan has run, so the server has no status of any",
      "draws": {
        "#106": "none",
        "#105": "none",
        "#10": "none",
        "#9": "none",
        "#8": "none",
        "#7": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=106,105,10,7"
      ],
      "repainted": [
        "106,105,10,7"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "drawn again: nothing is read",
      "draws": {
        "#106": "none",
        "#105": "none",
        "#10": "none",
        "#9": "none",
        "#8": "none",
        "#7": "none"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "the list's ask starts the scan: every row is read again, and the scan runs",
      "draws": {
        "#106": "none",
        "#105": "none",
        "#10": "none",
        "#9": "none",
        "#8": "none",
        "#7": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=106,105,10,7"
      ],
      "repainted": [
        "106,105,10,7"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": true
      }
    },
    {
      "step": "the next ask finds the scan running: nothing more is read",
      "draws": {
        "#106": "none",
        "#105": "none",
        "#10": "none",
        "#9": "none",
        "#8": "none",
        "#7": "none"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": true
      }
    },
    {
      "step": "the next says the scan ended: every row is read again, and each open row draws its verdict",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "ready (success): Ready to merge",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=106,105,10,7"
      ],
      "repainted": [
        "106,105,10,7"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "an ask that says the same scan ended reads nothing",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "ready (success): Ready to merge",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "a Pulls tab mounted again: its first paint, before it asks for a row, draws each glyph from the document's index, and its ask reads nothing",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "ready (success): Ready to merge",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "#105 is pushed: its verdict judged the old head, so it draws none, and it alone is read again; the server has no status for the new head",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "none",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=105"
      ],
      "repainted": [
        "105",
        "105"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "a scan starts and a read finds none running: the read's rows hold, and nothing more is read",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "none",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=106,105,10,7"
      ],
      "repainted": [
        "106,105,10,7"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "a read fails: each row keeps the glyph it had",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "none",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=106,105,10,7"
      ],
      "repainted": [
        "106,105,10,7"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": true
      }
    },
    {
      "step": "drawn again within the minute: nothing is read",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "none",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": true
      }
    },
    {
      "step": "a minute on, the failed read is asked again",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "none",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=106,105,10,7"
      ],
      "repainted": [
        "106,105,10,7"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "a stack's members, whose heads the menu does not know: #7, which the Pulls tab read, draws at once, #6 is read, and merged #8 is not asked",
      "draws": {
        "#7": "checks_pending (attention): Checks pending",
        "#6": "ready (success): Ready to merge",
        "#8": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=6"
      ],
      "repainted": [
        "6"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "opened again within the minute: nothing is read",
      "draws": {
        "#7": "checks_pending (attention): Checks pending",
        "#6": "ready (success): Ready to merge",
        "#8": "none"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "a minute on, opened again: each member is read again, once: #7 by the Pulls tab's lane, which draws it too and is told it is due, and #6 by the menu's",
      "draws": {
        "#7": "checks_pending (attention): Checks pending",
        "#6": "ready (success): Ready to merge",
        "#8": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=7",
        "GET /api/plugin/github/pull-statuses?numbers=6"
      ],
      "repainted": [
        "7",
        "7,6",
        "7",
        "7",
        "6"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "a scan the lane did not hear start ends before the next ask, which says when: every row is read again",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "none",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=106,105,10,7"
      ],
      "repainted": [
        "106,105,10,7"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "the next ask says the same: nothing is read",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "none",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "a pull request page reads #7's status itself, newer than the scan's: #7 alone is read again",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "none",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=7"
      ],
      "repainted": [
        "7",
        "7"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "the page reads the same status again as it polls: nothing is read",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "none",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "#106 is marked a draft: its verdict judged it open, so it draws none; its read again fails, and it still draws none",
      "draws": {
        "#106": "none",
        "#105": "none",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=106"
      ],
      "repainted": [
        "106",
        "106"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "a minute on, the draft is read again, and draws the server's verdict on it",
      "draws": {
        "#106": "ready_for_review (success): Ready for review",
        "#105": "none",
        "#10": "conflicts (severe): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=106"
      ],
      "repainted": [
        "106"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "a server with no repository: one answer, and no row draws a glyph",
      "draws": {
        "#106": "none",
        "#105": "none",
        "#10": "none",
        "#9": "none",
        "#8": "none",
        "#7": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=106,105,10,7"
      ],
      "repainted": [
        "every row",
        "106,105,10,7"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    }
  ]
}
? 0
```

`panel` mounts the production Pulls panel over a stand-in for the DOM, on the recorded
list, and prints six rows as drawn: an open pull request of each tone, ready to merge,
waiting on its checks, and a draft with conflicts, a merged and a closed one, and #105,
which is pushed. A row’s `glyph` is its verdict and tone, in the tone’s ink, and its
`label` the label after it, in the text’s; both are hidden from assistive technology
(`hidden`), and the run’s `words`, out of view after the state icon, say the label, so
the link’s `name` says the verdict after the state, as the state icon says the state.
`last` is the last line’s parts: the change line, the readiness’s column, and the age,
there on every row, so a glyph that arrives moves nothing.
A panel disposed with a read queued for the browser’s idle time cancels it, and reads
nothing once it is gone; and a panel mounted again in the document draws each glyph in
its first paint, before any read.

`menu` mounts the production stack menu of #7’s page: #7’s readiness is its page’s own,
and the others’ are read as the menu opens, each member’s line ending with its glyph’s
cell, empty for a member with none; and another page’s menu, opened once the Pulls tab
has read a member, draws its glyph on its first open and reads nothing.

`reads` draws one pull request on every kind of surface at once, each by the head it
knows: two Pulls tabs by the catalog’s, a stack’s page and a stack menu by none, and a
surface whose record lags by its record’s. Each asks, the browser runs their idle work,
and their reads land, in shuffled orders, many turns between two things that say the row
changed; `reads` is how often it was read for each, at most once, and `draws` what each
surface draws: the verdict wherever the head it knows is the one judged, or it knows
none.

```console
$ node tests/dom/github-pulls-readiness-surfaces-session.js
{
  "panel": [
    {
      "step": "mounted, and the reader scrolls to the end of the list's first window, which reads its second: every row's readiness column is there and empty; nothing is read yet",
      "rows": {
        "#106": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Work item 106 #106 · contributor · 1m"
        },
        "#105": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Work item 105 #105 · contributor · 1m"
        },
        "#10": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Draft WIP: draft the next page #10 · maintainer · 1m"
        },
        "#9": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Closed spam #9 · ghost · 1m"
        },
        "#8": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Merged Say more in the guide #8 · maintainer · 1m"
        },
        "#7": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Count to two in the app #7 · forker · 1m"
        }
      },
      "requests": []
    },
    {
      "step": "idle: one read for the open rows drawn; no scan has run, so the server has no status of any, and every column stays empty",
      "rows": {
        "#106": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Work item 106 #106 · contributor · 1m"
        },
        "#105": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Work item 105 #105 · contributor · 1m"
        },
        "#10": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Draft WIP: draft the next page #10 · maintainer · 1m"
        },
        "#9": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Closed spam #9 · ghost · 1m"
        },
        "#8": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Merged Say more in the guide #8 · maintainer · 1m"
        },
        "#7": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Count to two in the app #7 · forker · 1m"
        }
      },
      "requests": [
        "GET /api/plugin/github/pull-statuses?numbers=106,105,104,103,102,101,100,99,… (100)"
      ]
    },
    {
      "step": "the reader presses Refresh, and the ask starts the scan: the rows are read again",
      "rows": {
        "#106": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Work item 106 #106 · contributor · 1m"
        },
        "#105": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Work item 105 #105 · contributor · 1m"
        },
        "#10": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Draft WIP: draft the next page #10 · maintainer · 1m"
        },
        "#9": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Closed spam #9 · ghost · 1m"
        },
        "#8": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Merged Say more in the guide #8 · maintainer · 1m"
        },
        "#7": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Count to two in the app #7 · forker · 1m"
        }
      },
      "requests": [
        "POST /api/plugin/github/pulls-refresh: status_scan=started",
        "GET /api/plugin/github/pull-statuses?numbers=106,105,104,103,102,101,100,99,… (100)"
      ]
    },
    {
      "step": "Refresh again: the ask finds the scan over, and the rows are read again; each open row draws its verdict, the merged and the closed none",
      "rows": {
        "#106": {
          "glyph": "ready (success)",
          "label": "Ready to merge",
          "hidden": true,
          "words": "Ready to merge",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Ready to merge Work item 106 #106 · contributor · 1m"
        },
        "#105": {
          "glyph": "ready (success)",
          "label": "Ready to merge",
          "hidden": true,
          "words": "Ready to merge",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Ready to merge Work item 105 #105 · contributor · 1m"
        },
        "#10": {
          "glyph": "conflicts (severe)",
          "label": "Merge conflicts",
          "hidden": true,
          "words": "Merge conflicts",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Draft Merge conflicts WIP: draft the next page #10 · maintainer · 1m"
        },
        "#9": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Closed spam #9 · ghost · 1m"
        },
        "#8": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Merged Say more in the guide #8 · maintainer · 1m"
        },
        "#7": {
          "glyph": "checks_pending (attention)",
          "label": "Checks pending",
          "hidden": true,
          "words": "Checks pending",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Checks pending Count to two in the app #7 · forker · 1m"
        }
      },
      "requests": [
        "POST /api/plugin/github/pulls-refresh: status_scan=not_due",
        "GET /api/plugin/github/pull-statuses?numbers=106,105,104,103,102,101,100,99,… (100)"
      ]
    },
    {
      "step": "a poll: the list names #105's new head, so its verdict, which judged the old one, is drawn no more, and #105 alone is read again; the server has no status for the new head",
      "rows": {
        "#106": {
          "glyph": "ready (success)",
          "label": "Ready to merge",
          "hidden": true,
          "words": "Ready to merge",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Ready to merge Work item 106 #106 · contributor · 1m"
        },
        "#105": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Work item 105 #105 · contributor · 1m"
        },
        "#10": {
          "glyph": "conflicts (severe)",
          "label": "Merge conflicts",
          "hidden": true,
          "words": "Merge conflicts",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Draft Merge conflicts WIP: draft the next page #10 · maintainer · 1m"
        },
        "#9": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Closed spam #9 · ghost · 1m"
        },
        "#8": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Merged Say more in the guide #8 · maintainer · 1m"
        },
        "#7": {
          "glyph": "checks_pending (attention)",
          "label": "Checks pending",
          "hidden": true,
          "words": "Checks pending",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Checks pending Count to two in the app #7 · forker · 1m"
        }
      },
      "requests": [
        "GET /api/plugin/github/pull-statuses?numbers=105"
      ]
    },
    {
      "step": "the ask starts a scan again, and the panel is disposed before the browser is idle: its queued read is cancelled, and nothing is read",
      "requests": [
        "POST /api/plugin/github/pulls-refresh: status_scan=started"
      ]
    },
    {
      "step": "the Pulls tab mounted again in the document: its first paint, before the browser is idle and before any read, draws each glyph the document's index holds",
      "rows": {
        "#106": {
          "glyph": "ready (success)",
          "label": "Ready to merge",
          "hidden": true,
          "words": "Ready to merge",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Ready to merge Work item 106 #106 · contributor · 1m"
        },
        "#105": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Work item 105 #105 · contributor · 1m"
        },
        "#10": {
          "glyph": "conflicts (severe)",
          "label": "Merge conflicts",
          "hidden": true,
          "words": "Merge conflicts",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Draft Merge conflicts WIP: draft the next page #10 · maintainer · 1m"
        },
        "#9": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Closed spam #9 · ghost · 1m"
        },
        "#8": {
          "glyph": null,
          "label": null,
          "hidden": true,
          "words": "",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Merged Say more in the guide #8 · maintainer · 1m"
        },
        "#7": {
          "glyph": "checks_pending (attention)",
          "label": "Checks pending",
          "hidden": true,
          "words": "Checks pending",
          "last": [
            "github-pulls-change",
            "github-pulls-readiness",
            "github-pulls-age"
          ],
          "name": "Open Checks pending Count to two in the app #7 · forker · 1m"
        }
      },
      "requests": []
    }
  ],
  "menu": [
    {
      "step": "the menu opens: #7, the page's own, says its page's verdict; #6 waits for its read, and merged #8 has none",
      "members": {
        "#8": {
          "parts": [
            "github-pull-state-icon",
            "github-pull-readiness-said",
            "github-pull-stack-member-copy",
            "github-pull-stack-member-readiness"
          ],
          "glyph": null,
          "hidden": true,
          "name": "Merged Stack change 8 3/3 #8"
        },
        "#7": {
          "parts": [
            "github-pull-state-icon",
            "github-pull-readiness-said",
            "github-pull-stack-member-copy",
            "github-pull-stack-member-readiness"
          ],
          "glyph": "checks_pending (attention)",
          "hidden": true,
          "name": "Open Checks pending Follow up 2/3 #7"
        },
        "#6": {
          "parts": [
            "github-pull-state-icon",
            "github-pull-readiness-said",
            "github-pull-stack-member-copy",
            "github-pull-stack-member-readiness"
          ],
          "glyph": null,
          "hidden": true,
          "name": "Count to two 1/3 #6"
        }
      },
      "asked": []
    },
    {
      "step": "idle: #6's read, and its verdict drawn in the open menu",
      "members": {
        "#8": {
          "parts": [
            "github-pull-state-icon",
            "github-pull-readiness-said",
            "github-pull-stack-member-copy",
            "github-pull-stack-member-readiness"
          ],
          "glyph": null,
          "hidden": true,
          "name": "Merged Stack change 8 3/3 #8"
        },
        "#7": {
          "parts": [
            "github-pull-state-icon",
            "github-pull-readiness-said",
            "github-pull-stack-member-copy",
            "github-pull-stack-member-readiness"
          ],
          "glyph": "checks_pending (attention)",
          "hidden": true,
          "name": "Open Checks pending Follow up 2/3 #7"
        },
        "#6": {
          "parts": [
            "github-pull-state-icon",
            "github-pull-readiness-said",
            "github-pull-stack-member-copy",
            "github-pull-stack-member-readiness"
          ],
          "glyph": "ready (success)",
          "hidden": true,
          "name": "Ready to merge Count to two 1/3 #6"
        }
      },
      "asked": [
        "menu: GET /api/plugin/github/pull-statuses?numbers=6"
      ]
    },
    {
      "step": "the Pulls tab has read #6 into the document's index; another page's menu opens: its first open draws #6's glyph, and reads nothing",
      "read_before": [
        "pulls: GET /api/plugin/github/pull-statuses?numbers=6"
      ],
      "members": {
        "#8": {
          "parts": [
            "github-pull-state-icon",
            "github-pull-readiness-said",
            "github-pull-stack-member-copy",
            "github-pull-stack-member-readiness"
          ],
          "glyph": null,
          "hidden": true,
          "name": "Merged Stack change 8 3/3 #8"
        },
        "#7": {
          "parts": [
            "github-pull-state-icon",
            "github-pull-readiness-said",
            "github-pull-stack-member-copy",
            "github-pull-stack-member-readiness"
          ],
          "glyph": "checks_pending (attention)",
          "hidden": true,
          "name": "Open Checks pending Follow up 2/3 #7"
        },
        "#6": {
          "parts": [
            "github-pull-state-icon",
            "github-pull-readiness-said",
            "github-pull-stack-member-copy",
            "github-pull-stack-member-readiness"
          ],
          "glyph": "ready (success)",
          "hidden": true,
          "name": "Ready to merge Count to two 1/3 #6"
        }
      },
      "asked": []
    }
  ],
  "reads": [
    {
      "change": "drawn first, and again and again",
      "reads": 1,
      "draws": {
        "a Pulls tab, by the catalog's head": "ready (success): Ready to merge",
        "another Pulls tab": "ready (success): Ready to merge",
        "a stack's page, by no head": "ready (success): Ready to merge",
        "a surface whose record lags, by its record's head": "none",
        "a stack menu, by no head and no state": "ready (success): Ready to merge"
      }
    },
    {
      "change": "drawn again and again, nothing changed",
      "reads": 0,
      "draws": {
        "a Pulls tab, by the catalog's head": "ready (success): Ready to merge",
        "another Pulls tab": "ready (success): Ready to merge",
        "a stack's page, by no head": "ready (success): Ready to merge",
        "a surface whose record lags, by its record's head": "none",
        "a stack menu, by no head and no state": "ready (success): Ready to merge"
      }
    },
    {
      "change": "the list's ask says the scan started",
      "reads": 1,
      "draws": {
        "a Pulls tab, by the catalog's head": "ready (success): Ready to merge",
        "another Pulls tab": "ready (success): Ready to merge",
        "a stack's page, by no head": "ready (success): Ready to merge",
        "a surface whose record lags, by its record's head": "none",
        "a stack menu, by no head and no state": "ready (success): Ready to merge"
      }
    },
    {
      "change": "an ask says a scan ended",
      "reads": 1,
      "draws": {
        "a Pulls tab, by the catalog's head": "ready (success): Ready to merge",
        "another Pulls tab": "ready (success): Ready to merge",
        "a stack's page, by no head": "ready (success): Ready to merge",
        "a surface whose record lags, by its record's head": "none",
        "a stack menu, by no head and no state": "ready (success): Ready to merge"
      }
    },
    {
      "change": "another tab's ask says that same scan ended",
      "reads": 0,
      "draws": {
        "a Pulls tab, by the catalog's head": "ready (success): Ready to merge",
        "another Pulls tab": "ready (success): Ready to merge",
        "a stack's page, by no head": "ready (success): Ready to merge",
        "a surface whose record lags, by its record's head": "none",
        "a stack menu, by no head and no state": "ready (success): Ready to merge"
      }
    },
    {
      "change": "a pull request page reads its status, newer than the answer's, and again as it polls",
      "reads": 1,
      "draws": {
        "a Pulls tab, by the catalog's head": "ready (success): Ready to merge",
        "another Pulls tab": "ready (success): Ready to merge",
        "a stack's page, by no head": "ready (success): Ready to merge",
        "a surface whose record lags, by its record's head": "none",
        "a stack menu, by no head and no state": "ready (success): Ready to merge"
      }
    },
    {
      "change": "a minute passes",
      "reads": 1,
      "draws": {
        "a Pulls tab, by the catalog's head": "ready (success): Ready to merge",
        "another Pulls tab": "ready (success): Ready to merge",
        "a stack's page, by no head": "ready (success): Ready to merge",
        "a surface whose record lags, by its record's head": "none",
        "a stack menu, by no head and no state": "ready (success): Ready to merge"
      }
    },
    {
      "change": "the list names a new head, which both Pulls tabs draw",
      "reads": 1,
      "draws": {
        "a Pulls tab, by the catalog's head": "none",
        "another Pulls tab": "none",
        "a stack's page, by no head": "none",
        "a surface whose record lags, by its record's head": "none",
        "a stack menu, by no head and no state": "none"
      }
    },
    {
      "change": "the lagging record catches up with that head",
      "reads": 0,
      "draws": {
        "a Pulls tab, by the catalog's head": "none",
        "another Pulls tab": "none",
        "a stack's page, by no head": "none",
        "a surface whose record lags, by its record's head": "none",
        "a stack menu, by no head and no state": "none"
      }
    }
  ],
  "invariants": {
    "panel": {
      "7": {
        "verdict": "checks_pending",
        "tone": "attention",
        "label": "Checks pending"
      },
      "8": null,
      "9": null,
      "10": {
        "verdict": "conflicts",
        "tone": "severe",
        "label": "Merge conflicts"
      },
      "105": {
        "verdict": "ready",
        "tone": "success",
        "label": "Ready to merge"
      },
      "106": {
        "verdict": "ready",
        "tone": "success",
        "label": "Ready to merge"
      }
    }
  }
}
? 0
```
