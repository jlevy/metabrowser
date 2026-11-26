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
every open pull request kept, which the list’s own ask starts (`POST pulls-refresh`).
This browserless session runs the production code that decides which rows are read and
what each draws, `builtin_plugins/github/row-readiness.js`, and that draws it,
`builtin_plugins/github/stack-member-row.js`, on the server’s own answers, which
`tests/test_github_pulls_readiness_session.py` records: before the scan, while it runs,
once it has ended, and after a push it has not read.

`lane` drives the lane alone, with the browser’s idle time and its clock in the
session’s hands. Each step’s `draws` is what each row draws: the verdict, its tone, and
its label, or `none`. `asked` is what the step read, the rows drawn in one request when
the browser is idle, and `lane` the lane’s own state.
A closed or merged row is never asked, and draws none.
A row’s answer holds until the list’s ask says the scan started, or ended once it was
heard running, or a read finds it over; until the row’s head or state moves; or, on a
stack’s member rows, which no ask reaches, until it is a minute old.
A verdict is drawn for the head it judged only, so a pushed row draws none until the
server judges the new head; a read that fails keeps each glyph and is asked again a
minute on; and a server with no GitHub repository answers once for every row.

`panel` mounts the production Pulls panel over a stand-in for the DOM, on the recorded
list, and prints six rows as drawn: an open pull request of each tone, ready to merge,
waiting on its checks, and a draft with conflicts, a merged and a closed one, and #105,
which is pushed. A row’s `glyph` is its verdict and tone, in the tone’s ink, and its
`label` the label after it, in the text’s; both are hidden from assistive technology
(`hidden`), and the run’s `words`, out of view after the state icon, say the label, so
the link’s `name` says the verdict after the state, as the state icon says the state.
`last` is the last line’s parts: the change line, the readiness’s column, and the age,
there on every row, so a glyph that arrives moves nothing.
Last, a panel disposed with a read queued for the browser’s idle time cancels it, and
reads nothing once it is gone.

`menu` mounts the production stack menu of #7’s page: #7’s readiness is its page’s own,
and the others’ are read as the menu opens, each member’s line ending with its glyph’s
cell, empty for a member with none.

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
      "step": "the next finds it over: every row is read again, and each open row draws its verdict",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "ready (success): Ready to merge",
        "#10": "conflicts (danger): Merge conflicts",
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
      "step": "an ask with the scan still over reads nothing",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "ready (success): Ready to merge",
        "#10": "conflicts (danger): Merge conflicts",
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
      "step": "a Pulls tab mounted again: each glyph at once, from the document's index",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "ready (success): Ready to merge",
        "#10": "conflicts (danger): Merge conflicts",
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
        "#10": "conflicts (danger): Merge conflicts",
        "#9": "none",
        "#8": "none",
        "#7": "checks_pending (attention): Checks pending"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=105"
      ],
      "repainted": [
        "105"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    },
    {
      "step": "a scan starts and a read finds it over: the read's rows hold, and nothing more is read",
      "draws": {
        "#106": "ready (success): Ready to merge",
        "#105": "none",
        "#10": "conflicts (danger): Merge conflicts",
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
        "#10": "conflicts (danger): Merge conflicts",
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
        "#10": "conflicts (danger): Merge conflicts",
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
        "#10": "conflicts (danger): Merge conflicts",
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
      "step": "a minute on, opened again: each member is read again",
      "draws": {
        "#7": "checks_pending (attention): Checks pending",
        "#6": "ready (success): Ready to merge",
        "#8": "none"
      },
      "asked": [
        "GET /api/plugin/github/pull-statuses?numbers=7,6"
      ],
      "repainted": [
        "7,6"
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
        "every row"
      ],
      "lane": {
        "wanted": [],
        "running": null,
        "scanning": false
      }
    }
  ],
  "panel": [
    {
      "step": "mounted: every row's readiness column is there and empty; nothing is read yet",
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
        "GET /api/plugin/github/pull-statuses?numbers=106,105,104,103,102,101,100,99,… (98)"
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
        "GET /api/plugin/github/pull-statuses?numbers=106,105,104,103,102,101,100,99,… (98)"
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
          "glyph": "conflicts (danger)",
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
        "GET /api/plugin/github/pull-statuses?numbers=106,105,104,103,102,101,100,99,… (98)"
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
          "glyph": "conflicts (danger)",
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
        "GET /api/plugin/github/pull-statuses?numbers=6"
      ]
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
        "tone": "danger",
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

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
