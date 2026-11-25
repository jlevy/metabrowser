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
  The first paint lists the members top first, each the stack menu’s member row, and
  holds the merge’s row and the pending size line and summary; the answer lands in the
  same rows, so nothing under the title moves.
  The Diff summary is drawn with what a pull request’s page passes, so it starts
  collapsed with no layer marks on its rows.
- `front`: the front page of 70, whose guide 10 carries, shows Guided Review and reads
  step 1 at the comparison the page draws, by its two commits and its key.
- `step`: the step draws a file of the stack as a patch, a Markdown file whole from the
  comparison drawn, and a file of 9 from 9’s own comparison.
  Its note is inserted against the page of the member that carries the guide, here 8’s,
  and its outside link is marked.
  Each file’s Open full diff opens it where it is a change: the stack’s Changes, or 9’s.
- `edited`: a new revision of the carrier’s record, while the comparison drawn is
  current, reads the step on screen again at that comparison.
- `moved`: another member moves the stack.
  The new comparison is offered, not swapped in: nothing is read again, and the next
  step is read at the comparison still drawn.
  An answer read at another comparison draws no document whole.
- `taken`: the reader takes the new comparison, and the guide is mounted again, its
  earlier views disposed, and read at the comparison now drawn.
- `left`: leaving the tab for Changes while a read is on its way disposes the view,
  aborts the read, and draws Changes as a pull request’s page draws its own, with no
  summary of its own and no layer marks; the header’s Diff summary is drawn once for
  each comparison the page drew.

```console
$ node tests/dom/github-stack-guide-mount-session.js
{
  "header": {
    "first_paint": [
      "title",
      "corner",
      {
        "members": [
          "WIP: draft the next page 2/2 · #10",
          "Say more in the guide 1/2 · #8"
        ]
      },
      {
        "merge": ""
      },
      {
        "size": "(pending)"
      },
      {
        "summary": "(pending)"
      }
    ],
    "settled": [
      "title",
      "corner",
      {
        "members": [
          "WIP: draft the next page 2/2 · #10",
          "Say more in the guide 1/2 · #8"
        ]
      },
      {
        "merge": "wip → topic"
      },
      {
        "size": "1 file changed"
      },
      {
        "summary": ""
      }
    ],
    "summary_drawing": {
      "openFile": "function"
    }
  },
  "front": {
    "tab": "Guided Review",
    "asks": "70 1 <base> <draft_head> ebfe45cd812c6d00f8d4a921576b31d7"
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
    "offer": "This stack has changed since its comparison was drawn. Show the new comparison",
    "reads_before_next": 2,
    "asks": "70 2 <base> <draft_head> ebfe45cd812c6d00f8d4a921576b31d7",
    "document_at": "<draft_head>"
  },
  "carrier_moved": {
    "asks": "70 3 <base> <draft_head> ebfe45cd812c6d00f8d4a921576b31d7",
    "step_refused": "This stack has moved since its comparison was drawn. Show the new comparison to read its guide.",
    "steps_kept": 3,
    "route_refused_step": "3",
    "reopened_reads": 0,
    "reopened_steps": 0
  },
  "taken": {
    "asks": "70 1 <moved_base> <moved_head> ffffffffffffffffffffffffffffffff",
    "earlier_views_disposed": true
  },
  "left": {
    "tab": "Changes",
    "read_aborted": true,
    "summaries_drawn": 2,
    "diffs_drawn": 2,
    "changes_drawing": {
      "summary": false,
      "types": null,
      "onTypes": "function",
      "markdownHoldMs": 200
    }
  }
}
? 0
```
