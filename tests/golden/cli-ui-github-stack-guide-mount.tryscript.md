---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Stack’s Page Mounted, and Its Guided Review

A native stack’s page at `/stack/<n>` shows the stack’s guide in Guided Review: the
`stack-review` block of the top-most member whose description has one, read by
`guided-review?stack=<n>` against a combined comparison of the stack.
This browserless session mounts the production `mountStackPage` in
`builtin_plugins/github/stack-page.js` with a stub SDK, on the stack route’s answer for
70 that `tests/test_cli_github_stack_golden.py` records, and answers the guide’s reads
itself. The navigation between steps is `github-guided-review-session.js`’s, and the
stack’s own state machine is `github-stack-page-session.js`’s; this session pins the
page’s glue between them.

- `header`: the header’s rows as the reader sees them, at the page’s first paint and
  once its answer has landed, with the Pulls tab having read the repository’s stacks, as
  it has when a stack button opens the page.
  The first paint lists the members top first, each the stack menu’s member row, ending
  in the author the stacks route names, 10’s, under their toggle, “2 Pulls”, closed; it
  holds the row of ages, the author’s row, the merge’s row, and the labels row a line
  tall, and the size line and summary pending.
  The answer lands in the same rows, naming 8’s author from its record too, so nothing
  under the title moves; the page is held out of sight until it does.
  A fetch’s age is said as of the clock, so it is printed as `<age>`. The Diff summary
  is drawn with what a pull request’s page passes, so it starts collapsed, as every Diff
  summary does.
- `members_toggle`: the members’ toggle starts closed, as the Diff summary does, and
  opens and closes the card it controls; an answer read while it is open leaves it open.
- `front`: the front page of 70, whose guide 10 carries, shows Guided Review and reads
  step 1 at the comparison the page draws, by its two commits and its key.
- `list`: its step list, which has no overview row, and whose steps are in no group, so
  each row is its number and its title from the list’s edge, the edge a group’s heading
  starts on, in a column one digit wide.
- `step`: the step draws a file of the stack as a patch, a Markdown file whole from the
  comparison drawn, and a file of 9 from 9’s own comparison.
  Its note is inserted against the page of the member that carries the guide, here 8’s,
  and its outside link is marked.
  Each file’s Open full diff opens it where it is a change: the stack’s Changes, or 9’s.
- `edited`: a member’s record catches up, to a head the comparison drawn already shows,
  so the stack’s key changes while its two commits and its files stay, and the carrier’s
  record has a new revision.
  Nothing the reader sees changes, so the comparison drawn stays, with no notice and the
  guide’s view kept, and the step on screen is read again at that comparison.
- `below_moved`: after the reader has pressed on the page, that member gains commits
  past the head its record caught up to.
  The new comparison is offered, not swapped in, its notice naming the member: nothing
  is read again, and the next step is read at the comparison still drawn.
  An answer read at another comparison draws no document whole.
- `carrier_moved`: the carrier moves with the stack and is pinned again, so a step not
  read yet is refused in the stack’s words, under the steps the guide keeps.
  The route’s own `stack_moved` says the comparison drawn may be gone, so the page reads
  the stack at once (`route_refused_reads_stack`), not at its next poll, and offers the
  new comparison.
- `taken`: the reader takes the new comparison, and the guide is mounted again, its
  earlier views disposed, and read at the comparison now drawn.
- `left`: leaving the tab for Changes while a read is on its way disposes the view,
  whose late answer draws nothing, while the read goes on for the document’s keep of the
  guide’s answers (`guide-reads.js`), and draws Changes as a pull request’s page draws
  its own, with no summary of its own; the header’s Diff summary is drawn once for each
  comparison the page drew.
- `failed`: Docs and Changes that could not load.
  Each says so in a pull request’s error notice, “Docs could not load.”
  or “Changes could not load.”, with Retry, whether the diff failed to draw or drew and
  then failed its first screen.
  Retry disposes the view a failed draw left and draws once more, and a Retry left
  behind by a tab switch, or pressed after the page is disposed, draws nothing.
  The page logs each failure once.
- `note_links`: what a note’s links open, with `static/repository-links.js` run whole,
  on a server whose tree is not the stack’s head.
  The note is drawn before the comparison is read, so a path-relative link opens the
  file on github.com at the head of the comparison drawn; once the read says what the
  comparison changes, the same note’s link to a changed file opens it in the stack’s
  Changes, in place, and a link to an unchanged file stays on github.com.
- `cold_without_labels` and `unknown_stack`: two more stacks’ headers from first paint
  to their answers.
- `members_readiness`: each member’s line ends with its readiness’s glyph in a cell, as
  in the stack menu (mb-3n21). The page reads the server’s verdict on its open members
  when the browser is idle, from the statuses
  `tests/test_github_pulls_readiness_session.py` records: #10, a draft, says “Merge
  conflicts” after its state and draws the glyph in the danger tone; #8 is merged, so it
  is not asked and its cell stays empty.

```console
$ node tests/dom/github-stack-guide-mount-session.js
{
  "header": {
    "first_paint": [
      "title",
      "corner",
      {
        "opened": "  "
      },
      {
        "meta": "·"
      },
      {
        "merge": ""
      },
      {
        "labels": []
      },
      {
        "size": "(pending)"
      },
      {
        "members": {
          "toggle": "2 Pulls",
          "held": false,
          "expanded": "false",
          "rows": [
            "WIP: draft the next page 2/2 · #10 · maintainer",
            "Say more in the guide 1/2 · #8"
          ]
        }
      },
      {
        "summary": "(pending)"
      }
    ],
    "settled": [
      "title",
      "corner",
      {
        "opened": "1 Pull Draft1 Pull Merged· Last opened now · Last update now "
      },
      {
        "meta": "maintainer wants to merge 2 commits·Fetched 5 min ago via GitHub CLIFetched 59 min ago via GitHub CLI"
      },
      {
        "merge": "wip → topic"
      },
      {
        "labels": [
          "bugfix",
          "shared design",
          "earnings analysis"
        ]
      },
      {
        "size": "1 file changed"
      },
      {
        "members": {
          "toggle": "2 Pulls",
          "held": false,
          "expanded": "false",
          "rows": [
            "WIP: draft the next page 2/2 · #10 · maintainer",
            "Say more in the guide 1/2 · #8 · maintainer"
          ]
        }
      },
      {
        "summary": ""
      }
    ],
    "members_toggle": {
      "first": {
        "expanded": "false",
        "collapsed": true,
        "controls": true
      },
      "opened": {
        "expanded": "true",
        "collapsed": false,
        "controls": true
      },
      "after_a_poll": {
        "expanded": "true",
        "collapsed": false,
        "controls": true
      },
      "closed": {
        "expanded": "false",
        "collapsed": true,
        "controls": true
      }
    },
    "summary_drawing": {
      "openFile": "function"
    }
  },
  "front": {
    "tab": "Guided Review",
    "asks": "70 1 <base> <draft_head> ebfe45cd812c6d00f8d4a921576b31d7"
  },
  "list": {
    "rows": [
      "github-pull-guide-steps-number: 1, github-pull-guide-steps-title: The layers",
      "github-pull-guide-steps-number: 2, github-pull-guide-steps-title: The draft",
      "github-pull-guide-steps-number: 3, github-pull-guide-steps-title: The plan"
    ],
    "style": "--github-pull-guide-loose-digits: 1"
  },
  "step": {
    "documents": [
      "docs/draft.md@<draft_head>"
    ],
    "patches": [
      "src/app.txt",
      "src/other.txt"
    ],
    "note_base": "https://github.com/octo/demo/pull/8",
    "marked": [
      "https://example.com/elsewhere"
    ],
    "opened": [
      "{\"number\":70,\"tab\":\"changes\",\"file\":\"src/app.txt\",\"stack\":true}",
      "{\"number\":9,\"tab\":\"files\",\"file\":\"src/other.txt\"}"
    ]
  },
  "edited": {
    "reads": 2,
    "asks": "70 1 <base> <draft_head> ebfe45cd812c6d00f8d4a921576b31d7"
  },
  "below_moved": {
    "offer": "#8 has 2 new commits. Show the new comparison",
    "reads_before_next": 2,
    "asks": "70 2 <base> <draft_head> ebfe45cd812c6d00f8d4a921576b31d7",
    "document_at": "<draft_head>"
  },
  "carrier_moved": {
    "asks": "70 3 <base> <draft_head> ebfe45cd812c6d00f8d4a921576b31d7",
    "step_refused": "This stack has moved since its comparison was drawn. Show the new comparison to read its guide.",
    "steps_kept": 3,
    "route_refused_step": "3",
    "route_refused_reads_stack": 1,
    "reopened_reads": 0,
    "reopened_steps": 0
  },
  "taken": {
    "asks": "70 1 <moved_base> <moved_head> ffffffffffffffffffffffffffffffff",
    "earlier_views_disposed": true
  },
  "left": {
    "tab": "Changes",
    "read_aborted": false,
    "summaries_drawn": 2,
    "diffs_drawn": 2,
    "changes_drawing": {
      "summary": false,
      "types": null,
      "onTypes": "function",
      "markdownHoldMs": 200
    }
  },
  "failed": {
    "docs": {
      "notice": "error: Docs could not load. Retry",
      "retry": "Retry",
      "after_retry": {
        "shows": "the diff",
        "draws": 1
      }
    },
    "changes": {
      "notice": "error: Changes could not load. Retry",
      "left_view_disposed": false,
      "after_retry": {
        "shows": "the diff",
        "draws": 1,
        "left_view_disposed": true
      }
    },
    "retry_after_tab_switch": {
      "shows": "the diff",
      "draws": 0
    },
    "retry_after_dispose": {
      "draws": 0
    },
    "logged": [
      "metabrowser github: the stack's diff could not load",
      "metabrowser github: the stack's diff could not load",
      "metabrowser github: the stack's diff could not load",
      "metabrowser github: the stack's diff could not load"
    ]
  },
  "cold_without_labels": {
    "first_paint": [
      "title",
      "corner",
      {
        "opened": "  "
      },
      {
        "meta": "·"
      },
      {
        "merge": ""
      },
      {
        "size": "(pending)"
      },
      {
        "members": {
          "toggle": "2 Pulls",
          "held": false,
          "expanded": "false",
          "rows": [
            "WIP: draft the next page 2/2 · #10 · maintainer",
            "Say more in the guide 1/2 · #8 · maintainer"
          ]
        }
      },
      {
        "summary": "(pending)"
      }
    ],
    "settled": [
      "title",
      "corner",
      {
        "opened": "1 Pull Draft1 Pull Merged· Last opened now · Last update now "
      },
      {
        "meta": "maintainer wants to merge 2 commits·Fetched 5 min ago via GitHub CLIFetched 59 min ago via GitHub CLI"
      },
      {
        "merge": "wip → topic"
      },
      {
        "size": "1 file changed"
      },
      {
        "members": {
          "toggle": "2 Pulls",
          "held": false,
          "expanded": "false",
          "rows": [
            "WIP: draft the next page 2/2 · #10 · maintainer",
            "Say more in the guide 1/2 · #8 · maintainer"
          ]
        }
      },
      {
        "summary": ""
      }
    ]
  },
  "unknown_stack": {
    "first_paint": [
      "title",
      "corner",
      {
        "opened": "  "
      },
      {
        "meta": "·"
      },
      {
        "merge": ""
      },
      {
        "labels": []
      },
      {
        "size": "(pending)"
      },
      {
        "members": {
          "toggle": "",
          "held": true,
          "expanded": "false",
          "rows": []
        }
      },
      {
        "summary": "(pending)"
      }
    ],
    "settled": [
      "title",
      "corner",
      {
        "opened": "1 Pull Draft1 Pull Merged· Last opened now · Last update now "
      },
      {
        "meta": "maintainer wants to merge 2 commits·Fetched 5 min ago via GitHub CLIFetched 59 min ago via GitHub CLI"
      },
      {
        "merge": "wip → topic"
      },
      {
        "labels": [
          "bugfix",
          "shared design",
          "earnings analysis"
        ]
      },
      {
        "size": "1 file changed"
      },
      {
        "members": {
          "toggle": "2 Pulls",
          "held": false,
          "expanded": "false",
          "rows": [
            "WIP: draft the next page 2/2 · #10 · maintainer",
            "Say more in the guide 1/2 · #8 · maintainer"
          ]
        }
      },
      {
        "summary": ""
      }
    ]
  },
  "note_links": {
    "before_the_read": [
      "the draft → https://github.com/octo/demo/blob/5555555555555555555555555555555555555555/docs/draft.md",
      "an unchanged file → https://github.com/octo/demo/blob/5555555555555555555555555555555555555555/src/same.txt"
    ],
    "once_read": [
      "the draft → /stack/70/changes/docs/draft.md",
      "an unchanged file → https://github.com/octo/demo/blob/5555555555555555555555555555555555555555/src/same.txt"
    ],
    "clicks": [
      "the draft: {\"number\":70,\"tab\":\"changes\",\"file\":\"docs/draft.md\",\"stack\":true}",
      "an unchanged file: the browser follows it"
    ]
  },
  "members_readiness": {
    "before_idle": [
      {
        "state": "draft",
        "words": "",
        "glyph": null,
        "cell_last": true
      },
      {
        "state": "merged",
        "words": "",
        "glyph": null,
        "cell_last": true
      }
    ],
    "asked": [
      "/api/plugin/github/pull-statuses?numbers=10"
    ],
    "after_idle": [
      {
        "state": "draft",
        "words": "Merge conflicts",
        "glyph": "conflicts (danger)",
        "cell_last": true
      },
      {
        "state": "merged",
        "words": "",
        "glyph": null,
        "cell_last": true
      }
    ]
  }
}
? 0
```
