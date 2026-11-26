---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Native Stack’s Page

A stack’s page at `/stack/<n>` draws the stack route’s answer (`pull_stack.py` in the
GitHub plugin): its members, the top member’s head and the base it merges into, and its
comparison from the bottom member’s merge base to the top member’s head, kept to the
files a layer changes.
`tests/test_cli_github_stack_golden.py` records the route’s answers for the GitHub
stand-in’s stacks in `tests/fixtures/github-stack-responses.json`: 70 while its members
have no record and then current, 71, whose top lacks 7, 72, which is not linear, 70 once
8 left it, asked `since` its earlier comparison, and 74, whose one member, 7, is
rewritten and then gains a commit, each asked `since` the comparison before.

This browserless session runs the production `builtin_plugins/github/stack-page.js` on
them.

- `tabs` is the tab each route shows: the front page is Guided Review for a stack whose
  member carries its guide, as 10 carries 70’s, and Changes for one with none, where
  Guided Review’s own address shows Changes too.
  Before the stack is read the front page marks no tab, so none is marked that the
  answer then moves from.
  A tab the page does not have, Files among them, since the stack’s files are its
  header’s Diff summary, shows what the front page shows.
- `guided` is the front page of 70, whose guide 10 carries, while the stack moves after
  the reader has moved on the page: the guide shown, the tab, and what the body does
  after each answer. While a member is fetched or the stack cannot be shown, Guided
  Review and its guide stay, as the drawn comparison does, and the guide is mounted
  again only when the reader takes the comparison offered; a description that no longer
  carries the guide turns the front page to Changes.
  `column` is the body’s column (`bodyInColumn`): the reading column, as a pull
  request’s body takes it, except on a drawn Docs or Changes, which take the full pane.
- `comparison` is what a new answer does to the comparison drawn (`answerAction`): the
  first is shown and the same one kept, and so is the one drawn when another looks the
  same, the same two commits and the same files, as 71’s does beside 70’s, since nothing
  the reader sees would change.
  One that looks different is drawn without a word before the reader does anything on
  the page, since a stack whose members’ records arrive one by one is catching up, not
  changing. After the reader’s move, it is held while a member it waits on is fetched,
  and then offered rather than swapped in under the reader.
  An answer asked `since` the comparison drawn has `moved` while the server keeps that
  comparison; one without it (`gone`) says the server no longer does, so what the body
  reads at it would be refused: one that looks the same is drawn in its place, and one
  that looks different is offered at once, though a member it waits on is fetched.
- `guide_current` is whether Guided Review reads an edit of its guide at the comparison
  drawn (`drawnCurrent`): when the stack’s comparison is the one drawn or looks the
  same, and not when the stack has moved past it.
- `changes` is what the notice of a new comparison says (`changeText`): what became of
  each member since the comparison drawn, top first, in one sentence, its new commits
  counted from the answer’s `moved`, or said to be rewritten when its branch no longer
  holds the head drawn; with no `moved` for the comparison drawn, a moved member was
  updated. A member whose new head the comparison drawn already shows, its record caught
  up, adds no commit and is named nowhere (`caught_up`). It names at most
  `CHANGES_NAMED` changes, one fewer and a count once there are more, says when only the
  order changed, and otherwise that the stack changed.
- `notices` is a reader on Changes of 70 while the stack moves: a comparison that looks
  the same leaves 70’s drawn, before the reader does anything on the page and after;
  before, one that looks different is drawn at once with no notice; after they scroll,
  one that looks different is held while 10 is fetched, then offered with what changed,
  and drawn when the reader takes it, which clears the notice.
  Once the server no longer keeps 70’s, one that looks the same is drawn in its place
  without a word, and one that looks different is offered while 10 is still fetched.
  `since` is the key each next read asks the route `since`: the comparison drawn, which
  the server keeps while the page asks.
- `caught_up` is a reader on Changes of 70 whose page draws it; 8’s record then catches
  up to a head the comparison drawn already shows, an answer that looks the same, and
  after the reader scrolls, 10 gains two commits.
  The notice names 10 alone: the answer kept from is what it says changed since, and the
  route counts no commit for 8.
- `reader_keys` is which keys the document hears count as the reader’s move on the page
  (`readerKey`): one pressed in the page, or with focus on nothing in particular, the
  body or the document’s root, and not a key typed into the shell’s own fields, nor a
  modifier pressed alone, which may begin a chord that leaves the page.
- `header` is the page’s header, row by row (`stackHeader`), a pull request’s header in
  a pull request’s order, said of the stack: its title, the View on GitHub corner, the
  row of ages, the author’s row, the merge it makes, its labels, the status line while
  it has something to say, the size line, its members, and the Diff summary.
  The row of ages leads with the tally of the members’ states (`tally`), a badge for
  each state some member is in, in the states’ order, and says when a member was last
  opened and last updated (`ages`). The author’s row says every author once, “want to
  merge” after two, with the commits of the members the top contains (`sentence`), and
  the freshness note says the oldest member record’s fetch, here five minutes before
  (`note`). The labels are every member’s, each once, top first, held while a member’s
  are not known (`null`), as 70’s are while its members have neither a record nor a list
  row. The first paint draws the members from the stack the Pulls tab knows, titled as
  its lists last read them and authored as the stacks route names them, and holds every
  other row a line tall, so each answer after it lands in the same rows: a member being
  fetched keeps its row’s title, the answer names the author of a member whose record
  has one where the stacks route named none (10’s), and only the status line comes and
  goes, as the members 71’s top lacks are said there.
  Until its answer the page is held cold for the quiet period, as a pull request’s page
  is until its record, and a stack that cannot be shown as one comparison, with none
  drawn, has no size line or summary.
- `sentences` is the author’s row’s sentence for a stack whose members are all merged,
  which names who merged them, for one with two authors, for one whose commits are not
  all counted, which says its action alone, and for one with no members, which has none.
- `size_inputs` is what the size line is drawn from for the comparison drawn: the
  answer’s commits and sizes, each left out while not known, and the files the Diff
  summary counts.
- `drawing` is the stack’s own part of what the page passes the diff view for Docs and
  Changes: the stack’s comparison and Docs’ word for no documents.
  The session holds that the rest is a pull request’s drawings, each value the shared
  drawing’s, with no summary of their own and the first screen’s Markdown held as a pull
  request’s page holds it.
- `said` is the line about members the top lacks, and what the page says for a stack it
  cannot show as one comparison.
- `delays` is the poll’s cadence: soon while a member is being asked for or fetched,
  otherwise at the top member’s probe interval, slowly without one, and not at all out
  of sight (`null`): a hidden page reads the stack again when it is shown.
- `sent` and `rendered` are the controller over a scripted poll: pending, current, an
  unchanged answer, then another comparison that looks the same (71’s answer standing in
  for 70 moved, asked `since` 70’s), which leaves 70’s drawn.
  Each read after a comparison is drawn asks `since` it.
  Each pending member is asked for at its head, a member with no record as the reader’s
  own open of it (`retry`), and the top member’s automatic ask is sent at its interval
  with the record revision the stack route names, so its answer leaves the record out.
  `failed` lists the members whose fetch ended without a record.
- `recovery` is a read that fails while an answer is drawn, which says so in the page’s
  own words and not the route’s, and then one that finds the drawn answer current again
  (a 304), which ends the failure.
- `cold` is a stack of ten members with no record on a server that fetches eight at once
  and refuses the rest (429). A refused member is asked for again after 2, 4, 8, then 16
  s until its fetch starts.
  One whose fetch ends without a record is named as failed, with a Retry, once a second
  read finds it so, and the reader’s Retry asks for it again.
  Once nothing is being asked for or fetched, the page reads at the slow cadence
  (`delay_after_failure`).
- `one_loop` is a read asked for while one is on its way: it starts no second loop, and
  is made once the first answer is drawn, which leaves one timer.
- `absent_ask` is a member’s fetch the server took while the stack was pending, which
  ends without moving the member once the stack is not linear: the ask ends there as on
  any other answer, and the page reads at the absent stack’s cadence, not every second.
- `ended_race` is the reader’s fetch of a member with no record, one answer showing it
  ended before the record it wrote is read, and the next read having it.
  The page confirms an ended fetch with one more read before it names the member as
  failed, so it names none, and the stack is current a second later.
- `body` is the page’s body over a reader who opens `docs/draft.md` in Changes while the
  stack moves. The file is scrolled to when its diff is first drawn and when the reader
  opens it again, never on a later answer.
  While a member is pending or its fetch has failed, and when another comparison
  arrives, the drawn comparison stays and the header’s status line says why, and what
  changed, until the reader takes the new one, which draws it.
  A stack that can no longer be shown as one keeps the comparison drawn; with nothing
  drawn, the body says what is missing.
  `column` is the body’s column, as under `guided`: the full pane once Changes is drawn,
  and the reading column for a notice or a wait with nothing drawn.
- `order` is the header’s order of 71’s members, the top first, as every stack menu
  lists them.

```console
$ node tests/dom/github-stack-page-session.js
{
  "tabs": {
    "guided": {
      "(front)": "guided",
      "guided": "guided",
      "files": "guided",
      "docs": "docs",
      "changes": "changes",
      "conversation": "guided"
    },
    "unguided": {
      "(front)": "changes",
      "guided": "changes",
      "files": "changes",
      "docs": "docs",
      "changes": "changes",
      "conversation": "changes"
    },
    "unread": {
      "(front)": "",
      "guided": "guided",
      "files": "",
      "docs": "docs",
      "changes": "changes",
      "conversation": ""
    }
  },
  "guided": [
    {
      "step": "before any answer",
      "guide": null,
      "tab": "",
      "do": "wait",
      "drawn": null,
      "column": "reading"
    },
    {
      "step": "current",
      "guide": "#10",
      "tab": "guided",
      "do": "mount guided",
      "drawn": "current",
      "column": "reading"
    },
    {
      "step": "a member's push, fetched",
      "guide": "#10",
      "tab": "guided",
      "do": "keep",
      "drawn": "current",
      "column": "reading"
    },
    {
      "step": "current again, another comparison",
      "guide": "#10",
      "tab": "guided",
      "do": "keep",
      "drawn": "current",
      "column": "reading"
    },
    {
      "step": "the reader takes it",
      "guide": "#10",
      "tab": "guided",
      "do": "mount guided",
      "drawn": "other",
      "column": "reading"
    },
    {
      "step": "the stack cannot be shown",
      "guide": "#10",
      "tab": "guided",
      "do": "keep",
      "drawn": "other",
      "column": "reading"
    },
    {
      "step": "the guide's block removed",
      "guide": null,
      "tab": "changes",
      "do": "mount changes",
      "drawn": "other",
      "column": "full pane"
    }
  ],
  "comparison": [
    [
      "nothing drawn, pending",
      "wait"
    ],
    [
      "nothing drawn, current",
      "show"
    ],
    [
      "drawn, the same answer",
      "keep"
    ],
    [
      "drawn, the stack now absent",
      "keep"
    ],
    [
      "drawn, another that looks the same",
      "keep"
    ],
    [
      "drawn, another that looks the same, gone",
      "adopt"
    ],
    [
      "drawn, another, before the reader's move",
      "adopt"
    ],
    [
      "drawn, another, after the reader's move",
      "offer"
    ],
    [
      "drawn, another, while 10 is fetched",
      "hold"
    ],
    [
      "drawn, another, once 10's fetch failed",
      "offer"
    ],
    [
      "drawn, another, while 10 is fetched, gone",
      "offer"
    ]
  ],
  "guide_current": [
    [
      "nothing drawn",
      null
    ],
    [
      "the same answer",
      true
    ],
    [
      "another that looks the same",
      true
    ],
    [
      "another",
      false
    ],
    [
      "the stack now absent",
      null
    ]
  ],
  "changes": {
    "left": "#8 left the stack.",
    "joined": "#8 joined the stack.",
    "one_new_commit": "#7 has 1 new commit.",
    "rewritten": "#7 was rewritten.",
    "not_asked_since": "#7 was updated.",
    "caught_up": "This stack has changed since its comparison was drawn.",
    "three": "#11 joined the stack, #10 has 2 new commits, and #7 was closed.",
    "four": "#12 joined the stack, #11 joined the stack, and 2 more pull requests changed.",
    "reordered": "The stack’s order changed.",
    "nothing_named": "This stack has changed since its comparison was drawn."
  },
  "notices": [
    {
      "step": "70, drawn",
      "do": "mount changes",
      "drawn": "70",
      "notices": [],
      "since": "70"
    },
    {
      "step": "looks the same, before the reader's move: 70's stays",
      "do": "keep",
      "drawn": "70",
      "notices": [
        "The top of this stack does not contain #7, so this view leaves out its changes. Open it to see them."
      ],
      "since": "70"
    },
    {
      "step": "looks different, before the reader's move: drawn at once",
      "do": "mount changes",
      "drawn": "70 without 8",
      "notices": [],
      "since": "70 without 8"
    },
    {
      "step": "70 again, drawn",
      "do": "mount changes",
      "drawn": "70",
      "notices": [],
      "since": "70"
    },
    {
      "step": "looks the same, after the reader scrolls: 70's stays",
      "do": "keep",
      "drawn": "70",
      "notices": [
        "The top of this stack does not contain #7, so this view leaves out its changes. Open it to see them."
      ],
      "since": "70"
    },
    {
      "step": "70's again",
      "do": "keep",
      "drawn": "70",
      "notices": [],
      "since": "70"
    },
    {
      "step": "looks different while 10 is fetched: held",
      "do": "keep",
      "drawn": "70",
      "notices": [
        "Fetching #10 before its new comparison can be shown."
      ],
      "since": "70"
    },
    {
      "step": "looks different, 10 fetched: offered",
      "do": "keep",
      "drawn": "70",
      "notices": [
        "#8 left the stack. [take]"
      ],
      "since": "70"
    },
    {
      "step": "the reader takes it",
      "do": "mount changes",
      "drawn": "70 without 8",
      "notices": [],
      "since": "70 without 8"
    },
    {
      "step": "70 once more, drawn",
      "do": "mount changes",
      "drawn": "70",
      "notices": [],
      "since": "70"
    },
    {
      "step": "looks the same, 70's gone: drawn in its place",
      "do": "mount changes",
      "drawn": "71",
      "notices": [
        "The top of this stack does not contain #7, so this view leaves out its changes. Open it to see them."
      ],
      "since": "71"
    },
    {
      "step": "70 drawn again",
      "do": "mount changes",
      "drawn": "70",
      "notices": [],
      "since": "70"
    },
    {
      "step": "looks different while 10 is fetched, 70's gone: offered",
      "do": "keep",
      "drawn": "70",
      "notices": [
        "#8 left the stack. [take]"
      ],
      "since": "70"
    },
    {
      "step": "the reader takes it, 70's gone",
      "do": "mount changes",
      "drawn": "70 without 8",
      "notices": [],
      "since": "70 without 8"
    }
  ],
  "caught_up": [
    {
      "step": "70, drawn",
      "action": "show",
      "drawn": "70",
      "notices": []
    },
    {
      "step": "8's record catches up, looks the same: kept",
      "action": "keep",
      "drawn": "70",
      "notices": []
    },
    {
      "step": "the reader scrolls; 10 gains two commits: offered",
      "action": "offer",
      "drawn": "70",
      "notices": [
        "#10 has 2 new commits. [take]"
      ]
    }
  ],
  "reader_keys": [
    [
      "j in the page",
      true
    ],
    [
      "Enter on the page's link",
      true
    ],
    [
      "j on the body",
      true
    ],
    [
      "Escape on the root",
      true
    ],
    [
      "a in the shell's search field",
      false
    ],
    [
      "Meta alone in the page",
      false
    ],
    [
      "Shift alone on the body",
      false
    ],
    [
      "Control alone on the body",
      false
    ],
    [
      "Alt alone on the body",
      false
    ]
  ],
  "header": {
    "first_paint": {
      "cold": true,
      "rows": "title, corner, opened, meta, merge, labels, size, members, summary",
      "tally": [],
      "ages": null,
      "sentence": null,
      "note": null,
      "labels": null,
      "members": [
        "(unknown) WIP: draft the next page 2/2 · #10",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": null,
      "status": [],
      "comparison": "pending"
    },
    "pending": {
      "cold": false,
      "rows": "title, corner, opened, meta, merge, labels, size, members, summary",
      "tally": [],
      "ages": {
        "opened": null,
        "updated": null
      },
      "sentence": null,
      "note": null,
      "labels": null,
      "members": [
        "(unknown) WIP: draft the next page 2/2 · #10",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": null,
      "status": [],
      "comparison": "pending"
    },
    "current": {
      "cold": false,
      "rows": "title, corner, opened, meta, merge, labels, size, members, summary",
      "tally": [
        "draft: 1 Pull Draft",
        "merged: 1 Pull Merged"
      ],
      "ages": {
        "opened": "2026-09-16T10:57:23Z",
        "updated": "2026-09-16T17:39:01Z"
      },
      "sentence": "maintainer wants to merge 2 commits",
      "note": "Fetched 5 min ago via GitHub CLI",
      "labels": [
        "bugfix #d73a4a",
        "shared design #0e8a16",
        "earnings analysis #5319e7"
      ],
      "members": [
        "draft WIP: draft the next page 2/2 · #10 · maintainer",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": "wip → topic",
      "status": [],
      "comparison": "drawn"
    },
    "lacking": {
      "cold": false,
      "rows": "title, corner, opened, meta, merge, labels, status, size, members, summary",
      "tally": [
        "draft: 1 Pull Draft",
        "open: 1 Pull Open",
        "merged: 1 Pull Merged"
      ],
      "ages": {
        "opened": "2026-09-16T10:57:23Z",
        "updated": "2026-09-16T17:39:01Z"
      },
      "sentence": "maintainer, forker want to merge 2 commits",
      "note": "Fetched 5 min ago via GitHub CLI",
      "labels": [
        "bugfix #d73a4a",
        "shared design #0e8a16",
        "enhancement #2700af",
        "earnings analysis #5319e7"
      ],
      "members": [
        "draft WIP: draft the next page 3/3 · #10 · maintainer",
        "open Count to two in the app 2/3 · #7 · forker",
        "merged Say more in the guide 1/3 · #8 · maintainer"
      ],
      "merge": "wip → topic",
      "status": [
        "The top of this stack does not contain #7, so this view leaves out its changes. Open it to see them."
      ],
      "comparison": "drawn"
    },
    "unknown_first_paint": {
      "cold": true,
      "rows": "title, corner, opened, meta, merge, labels, size, members, summary",
      "tally": [],
      "ages": null,
      "sentence": null,
      "note": null,
      "labels": null,
      "members": null,
      "merge": null,
      "status": [],
      "comparison": "pending"
    },
    "unknown_not_linear": {
      "cold": false,
      "rows": "title, corner, opened, meta, merge, labels, members",
      "tally": [
        "draft: 1 Pull Draft",
        "merged: 1 Pull Merged"
      ],
      "ages": {
        "opened": "2026-09-16T10:57:23Z",
        "updated": "2026-09-16T17:39:01Z"
      },
      "sentence": "maintainer wants to merge 2 commits",
      "note": "Fetched 5 min ago via GitHub CLI",
      "labels": [
        "shared design #0e8a16",
        "earnings analysis #5319e7",
        "bugfix #d73a4a"
      ],
      "members": [
        "merged Say more in the guide 2/2 · #8 · maintainer",
        "draft WIP: draft the next page 1/2 · #10 · maintainer"
      ],
      "merge": "guide-more → topic",
      "status": [],
      "comparison": "none"
    },
    "labelled_first_paint": {
      "cold": true,
      "rows": "title, corner, opened, meta, merge, labels, size, members, summary",
      "tally": [],
      "ages": null,
      "sentence": null,
      "note": null,
      "labels": [
        "earnings analysis",
        "bugfix",
        "shared design"
      ],
      "members": [
        "(unknown) WIP: draft the next page 2/2 · #10",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": null,
      "status": [],
      "comparison": "pending"
    },
    "bare_first_paint": {
      "cold": true,
      "rows": "title, corner, opened, meta, merge, size, members, summary",
      "tally": [],
      "ages": null,
      "sentence": null,
      "note": null,
      "labels": [],
      "members": [
        "(unknown) WIP: draft the next page 2/2 · #10",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": null,
      "status": [],
      "comparison": "pending"
    },
    "bare_current": {
      "cold": false,
      "rows": "title, corner, opened, meta, merge, size, members, summary",
      "tally": [
        "draft: 1 Pull Draft",
        "merged: 1 Pull Merged"
      ],
      "ages": {
        "opened": "2026-09-16T10:57:23Z",
        "updated": "2026-09-16T17:39:01Z"
      },
      "sentence": "maintainer wants to merge 2 commits",
      "note": "Fetched 5 min ago via GitHub CLI",
      "labels": [],
      "members": [
        "draft WIP: draft the next page 2/2 · #10 · maintainer",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": "wip → topic",
      "status": [],
      "comparison": "drawn"
    },
    "held_labels_answered_bare": {
      "cold": false,
      "rows": "title, corner, opened, meta, merge, size, members, summary",
      "tally": [
        "draft: 1 Pull Draft",
        "merged: 1 Pull Merged"
      ],
      "ages": {
        "opened": "2026-09-16T10:57:23Z",
        "updated": "2026-09-16T17:39:01Z"
      },
      "sentence": "maintainer wants to merge 2 commits",
      "note": "Fetched 5 min ago via GitHub CLI",
      "labels": [],
      "members": [
        "draft WIP: draft the next page 2/2 · #10 · maintainer",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": "wip → topic",
      "status": [],
      "comparison": "drawn"
    },
    "offline_behind": {
      "cold": false,
      "rows": "title, corner, opened, meta, merge, labels, size, members, summary",
      "tally": [
        "draft: 1 Pull Draft",
        "merged: 1 Pull Merged"
      ],
      "ages": {
        "opened": "2026-09-16T10:57:23Z",
        "updated": "2026-09-16T17:39:01Z"
      },
      "sentence": "maintainer wants to merge 2 commits",
      "note": "Offline · fetched 5 min ago via GitHub CLI",
      "labels": [
        "bugfix #d73a4a",
        "shared design #0e8a16",
        "earnings analysis #5319e7"
      ],
      "members": [
        "draft WIP: draft the next page 2/2 · #10 · maintainer",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": "wip → topic",
      "status": [],
      "comparison": "drawn"
    },
    "offline_current": {
      "cold": false,
      "rows": "title, corner, opened, meta, merge, labels, size, members, summary",
      "tally": [
        "draft: 1 Pull Draft",
        "merged: 1 Pull Merged"
      ],
      "ages": {
        "opened": "2026-09-16T10:57:23Z",
        "updated": "2026-09-16T17:39:01Z"
      },
      "sentence": "maintainer wants to merge 2 commits",
      "note": "Fetched 5 min ago via GitHub CLI",
      "labels": [
        "bugfix #d73a4a",
        "shared design #0e8a16",
        "earnings analysis #5319e7"
      ],
      "members": [
        "draft WIP: draft the next page 2/2 · #10 · maintainer",
        "merged Say more in the guide 1/2 · #8 · maintainer"
      ],
      "merge": "wip → topic",
      "status": [],
      "comparison": "drawn"
    }
  },
  "sentences": {
    "all_merged": {
      "actors": [
        {
          "login": "octo",
          "avatar": null
        }
      ],
      "action": "merged 2 commits"
    },
    "all_merged_no_merger": {
      "actors": [],
      "action": "merged 2 commits"
    },
    "two_authors": {
      "actors": [
        {
          "login": "maintainer",
          "avatar": null
        },
        {
          "login": "forker",
          "avatar": null
        }
      ],
      "action": "want to merge 2 commits"
    },
    "no_commits_counted": {
      "actors": [
        {
          "login": "maintainer",
          "avatar": null
        }
      ],
      "action": "wants to merge"
    },
    "no_members": null,
    "no_authors": null
  },
  "tally_order": [
    "5 Pulls Draft",
    "2 Pulls Open",
    "2 Pulls Merged",
    "1 Pull Closed"
  ],
  "size_inputs": {
    "current": {
      "commits": 2,
      "files": 1,
      "pushedBytes": null,
      "diffBytes": null
    },
    "sized": {
      "commits": 2,
      "files": 1,
      "pushedBytes": 380,
      "diffBytes": 741
    },
    "pending": {
      "files": null,
      "pushedBytes": null,
      "diffBytes": null
    },
    "none": {
      "files": null,
      "pushedBytes": null,
      "diffBytes": null
    }
  },
  "drawing": {
    "comparison": {
      "left": "<base>",
      "right": "<draft_head>",
      "base_policy": "direct",
      "route": "/api/plugin/github/stack-comparison?number=70&left=<base>&right=<draft_head>&base_policy=direct&key=ebfe45cd812c6d00f8d4a921576b31d7&build=<BUILD>&store=<STORE>",
      "image_route": "/api/plugin/github/pull-image?stack=70&left=<base>&right=<draft_head>&store=<STORE>",
      "rendered_route": "/api/plugin/github/pull-rendered-diff?stack=70&left=<base>&right=<draft_head>&store=<STORE>",
      "branch": null
    },
    "docs_empty": "No documents changed in this stack."
  },
  "said": {
    "lacking": "The top of this stack does not contain #7, so this view leaves out its changes. Open it to see them.",
    "lacking_none": null,
    "two_lacking": "The top of this stack does not contain #7 and #9, so this view leaves out each one’s changes. Open each to see them.",
    "not_linear": "This stack’s changes cannot be shown together. Open each pull request for its changes.",
    "unknown": "This stack cannot be shown."
  },
  "delays": {
    "pending_visible": 1000,
    "pending_none_asked": 30000,
    "current_visible": 5000,
    "current_hidden": null
  },
  "sent": [
    {
      "method": "GET",
      "route": "/api/plugin/github/stack?number=70"
    },
    {
      "method": "POST",
      "route": "/api/plugin/github/pull-refresh",
      "body": {
        "number": 8,
        "retry": true
      }
    },
    {
      "method": "POST",
      "route": "/api/plugin/github/pull-refresh",
      "body": {
        "number": 10,
        "retry": true
      }
    },
    {
      "method": "GET",
      "route": "/api/plugin/github/stack?number=70",
      "etag": "\"pending\""
    },
    {
      "method": "POST",
      "route": "/api/plugin/github/pull-refresh",
      "body": {
        "number": 10,
        "held": "161cdf3eeeedf69a8203fbc796617cc789a010845c45b4a08d405766b45885d4"
      }
    },
    {
      "method": "GET",
      "route": "/api/plugin/github/stack?number=70&since=ebfe45cd812c6d00f8d4a921576b31d7",
      "etag": "\"current\""
    },
    {
      "method": "POST",
      "route": "/api/plugin/github/pull-refresh",
      "body": {
        "number": 10,
        "held": "161cdf3eeeedf69a8203fbc796617cc789a010845c45b4a08d405766b45885d4"
      }
    },
    {
      "method": "GET",
      "route": "/api/plugin/github/stack?number=70&since=ebfe45cd812c6d00f8d4a921576b31d7",
      "etag": "\"current\""
    },
    {
      "method": "POST",
      "route": "/api/plugin/github/pull-refresh",
      "body": {
        "number": 10,
        "held": "161cdf3eeeedf69a8203fbc796617cc789a010845c45b4a08d405766b45885d4"
      }
    }
  ],
  "rendered": [
    {
      "state": "pending",
      "pending": [
        8,
        10
      ],
      "lacking": [],
      "comparison": "wait",
      "error": null,
      "failed": []
    },
    {
      "state": "current",
      "pending": [],
      "lacking": [],
      "comparison": "show",
      "error": null,
      "failed": []
    },
    {
      "state": "current",
      "pending": [],
      "lacking": [
        7
      ],
      "comparison": "keep",
      "error": null,
      "failed": []
    }
  ],
  "recovery": [
    {
      "state": "current",
      "error": null
    },
    {
      "state": "current",
      "error": "Could not read this stack."
    },
    {
      "state": "current",
      "error": null
    }
  ],
  "cold": {
    "asked": [
      "0s #100 retry 202",
      "0s #101 retry 202",
      "0s #102 retry 202",
      "0s #103 retry 202",
      "0s #104 retry 202",
      "0s #105 retry 202",
      "0s #106 retry 202",
      "0s #107 retry 202",
      "0s #108 retry 429",
      "0s #109 retry 429",
      "2s #108 retry 429",
      "2s #109 retry 429",
      "6s #108 retry 202",
      "6s #109 retry 202",
      "10s #109 retry 202"
    ],
    "rendered": [
      {
        "at": "0s",
        "pending": [
          100,
          101,
          102,
          103,
          104,
          105,
          106,
          107,
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "1s",
        "pending": [
          100,
          101,
          102,
          103,
          104,
          105,
          106,
          107,
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "2s",
        "pending": [
          100,
          101,
          102,
          103,
          104,
          105,
          106,
          107,
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "3s",
        "pending": [
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "6s",
        "pending": [
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "7s",
        "pending": [
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "8s",
        "pending": [
          108,
          109
        ],
        "failed": []
      },
      {
        "at": "9s",
        "pending": [
          109
        ],
        "failed": []
      },
      {
        "at": "10s",
        "pending": [
          109
        ],
        "failed": [
          109
        ]
      },
      {
        "at": "10s",
        "pending": [
          109
        ],
        "failed": []
      },
      {
        "at": "10s",
        "pending": [
          109
        ],
        "failed": []
      },
      {
        "at": "11s",
        "pending": [
          109
        ],
        "failed": []
      },
      {
        "at": "12s",
        "pending": [
          109
        ],
        "failed": []
      },
      {
        "at": "13s",
        "pending": [],
        "failed": []
      }
    ],
    "delay_after_failure": 30000
  },
  "one_loop": {
    "during": {
      "gets": 1,
      "timers": 0
    },
    "after_first": {
      "gets": 2,
      "timers": 0
    },
    "after_second": {
      "gets": 2,
      "timers": 1
    }
  },
  "absent_ask": {
    "asked": [
      "0s #8 202"
    ],
    "reads": [
      "0s pending",
      "1s pending",
      "2s pending",
      "3s absent",
      "33s absent"
    ]
  },
  "ended_race": [
    {
      "at": "0s",
      "state": "pending",
      "failed": []
    },
    {
      "at": "1s",
      "state": "pending",
      "failed": []
    },
    {
      "at": "2s",
      "state": "current",
      "failed": []
    }
  ],
  "body": [
    {
      "step": "opened a file, nothing read",
      "do": "wait",
      "drawn": null,
      "column": "reading",
      "notices": []
    },
    {
      "step": "pending",
      "do": "notice",
      "text": "Fetching #8 and #10 before the stack can be shown.",
      "drawn": null,
      "column": "reading",
      "notices": []
    },
    {
      "step": "current",
      "do": "mount changes",
      "drawn": "current",
      "column": "full pane",
      "notices": []
    },
    {
      "step": "current, mounted",
      "do": "scroll",
      "file": "docs/draft.md",
      "drawn": "current",
      "column": "full pane",
      "notices": []
    },
    {
      "step": "current again, top revision moved",
      "do": "keep",
      "drawn": "current",
      "column": "full pane",
      "notices": []
    },
    {
      "step": "the reader opens the file again",
      "do": "scroll",
      "file": "docs/draft.md",
      "drawn": "current",
      "column": "full pane",
      "notices": []
    },
    {
      "step": "a member added on top, pending",
      "do": "keep",
      "drawn": "current",
      "column": "full pane",
      "notices": [
        "Fetching #11 before its new comparison can be shown."
      ]
    },
    {
      "step": "its fetch failed",
      "do": "keep",
      "drawn": "current",
      "column": "full pane",
      "notices": [
        "Could not fetch #11 from GitHub. [retry]"
      ]
    },
    {
      "step": "8 leaves instead: another comparison, offered",
      "do": "keep",
      "drawn": "current",
      "column": "full pane",
      "notices": [
        "#8 left the stack. [take]"
      ]
    },
    {
      "step": "the reader takes it",
      "do": "mount changes",
      "drawn": "other",
      "column": "full pane",
      "notices": []
    },
    {
      "step": "the stack can no longer be shown as one",
      "do": "keep",
      "drawn": "other",
      "column": "full pane",
      "notices": [
        "This stack’s changes cannot be shown together. Open each pull request for its changes."
      ]
    },
    {
      "step": "the reader opens Docs",
      "do": "mount docs",
      "drawn": "other",
      "column": "full pane",
      "notices": [
        "This stack’s changes cannot be shown together. Open each pull request for its changes."
      ]
    },
    {
      "step": "nothing drawn, a member's fetch failed",
      "do": "notice",
      "text": "Fetching #8 before the stack can be shown. Could not fetch #10 from GitHub.",
      "retry": true,
      "drawn": null,
      "column": "reading",
      "notices": []
    },
    {
      "step": "nothing drawn, not linear",
      "do": "notice",
      "text": "This stack’s changes cannot be shown together. Open each pull request for its changes.",
      "drawn": null,
      "column": "reading",
      "notices": []
    }
  ],
  "order": [
    10,
    7,
    8
  ]
}
? 0
```
