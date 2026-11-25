---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Stack’s Guided Review on Its Page

A native stack’s page at `/stack/<n>` shows the stack’s guide in Guided Review: the
`stack-review` block of the top-most member whose description has one, read by
`guided-review?stack=<n>` against a combined comparison of the stack.
This browserless session mounts the production `mountStackPage` in
`builtin_plugins/github/stack-page.js` with a stub SDK, on the stack route’s answer for
70 that `tests/test_cli_github_stack_golden.py` records, and answers the guide’s reads
itself. The navigation between steps is `github-guided-review-session.js`’s, and the
stack’s own state machine is `github-stack-page-session.js`’s; this session pins the
page’s glue between them.

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
- `left`: leaving the tab while a read is on its way disposes the view, aborts the read,
  and mounts Files.

```console
$ node tests/dom/github-stack-guide-mount-session.js
{
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
  "moved": {
    "offer": "This stack has changed since its comparison was drawn. Show the new comparison",
    "reads_before_next": 2,
    "asks": "70 2 <base> <draft_head> ebfe45cd812c6d00f8d4a921576b31d7",
    "documents_drawn_at_other_pins": 0
  },
  "taken": {
    "asks": "70 1 <base> <moved_head> ffffffffffffffffffffffffffffffff",
    "earlier_views_disposed": true
  },
  "left": {
    "tab": "Files",
    "read_aborted": true,
    "files_mounted": 1
  }
}
? 0
```
