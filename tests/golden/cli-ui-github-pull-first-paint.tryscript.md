---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Pull-Request Page, Conversation and Changes First Paints

How a pull request’s page first paints its conversation and its Changes.
The rest of the page is in
[`cli-ui-github-pull-page.tryscript.md`](cli-ui-github-pull-page.tryscript.md), which
this was split from to keep each transcript within the review budget
`devtools/check_goldens.py` sets.

The conversation’s first paint of a full record is laid out out of sight until the
Markdown of every text its first screen shows can be inserted, within
`DESCRIPTION_HOLD_MS`, and the page is not ready meanwhile (`firstVisit`, `comments`).
The first screen is the page’s own, measured from its top, not the view of a scrolled
page it replaces, and a text that comes into it as those above render is waited for too,
the next few past it asked for at once (`firstScreen`); a text it never waited for that
fails leaves the hold met.
Over the loading page only the body waits: the header paints the record at once, and any
loading blocks that had shown stay over the held body until it shows (`landing`,
`landingAfterBlocksShowed`), and a page replaced while held stays out of sight
(`cancelledWhileHeld`). A revisit and a refreshed record with the same text paint the
render kept for that text at once, keeping its node (`revisit`, `refreshedSameText`).
Past the bound the page shows with a placeholder in the text’s place and its Markdown
follows (`pastTheBound`). When the record follows a core preview, whose first paint is
spent, the comments in view are asked for and pending before the record’s frame paints
(`recordAfterCore`). The state badge’s first paint is the fresher of the cached record
and the repository’s list (`listedState`). Changes with rendered Markdown stays out of
sight until its first screen settles or `CHANGES_FIRST_SCREEN_MS` passes, and a page
that goes while it waits keeps it out of sight and records the wait as cancelled
(`changes`). The kept renders are bounded by count and by characters, descriptions apart
from other parts (`bounded`). Under a held first paint over the loading page the header
does not wait: its tab column is live and badged while Shift is held, all three keys
act, and a link that has focus keeps it, as at release (`tabKeysWhileHeld`). A stack
that arrives during the hold paints its menu at once, and Control-N and Control-P are
live and in the Shift strip and walk the stack, while N alone opens nothing.

```console
$ node tests/dom/github-pull-first-paint-behavior.js
{
  "firstVisit": "held, then final",
  "refreshedSameText": "kept",
  "revisit": "final at first paint",
  "pastTheBound": "a placeholder, then Markdown",
  "comments": {
    "texts": 5,
    "asked": 5,
    "plainAtReady": 0
  },
  "holdSpans": [
    "hidden met 1",
    "hidden bound 1"
  ],
  "landing": {
    "blocksBefore": true,
    "whileHeld": {
      "holding": true,
      "blocks": false,
      "heading": "Count to two in the app #7"
    },
    "final": true,
    "heading": "Count to two in the app #7"
  },
  "landingAfterBlocksShowed": {
    "whileHeld": {
      "holding": true,
      "sameBlocks": true,
      "cover": true,
      "heading": "Count to two in the app #7"
    },
    "shown": {
      "blocks": false,
      "holding": false,
      "final": true,
      "heading": "Count to two in the app #7"
    }
  },
  "cancelledWhileHeld": {
    "holding": true
  },
  "firstScreen": {
    "0": {
      "plainOnFirstScreenAtReady": [],
      "waitedFor": 3,
      "outcome": "met",
      "askedBeforeSecondAnswer": 3
    },
    "5000": {
      "plainOnFirstScreenAtReady": [],
      "waitedFor": 3,
      "outcome": "met",
      "askedBeforeSecondAnswer": 3
    },
    "failsPastTheScreen": {
      "plainOnFirstScreenAtReady": [],
      "waitedFor": 2,
      "outcome": "met",
      "askedBeforeSecondAnswer": 4
    },
    "cascade": {
      "plainOnFirstScreenAtReady": [],
      "waitedFor": 6,
      "outcome": "met",
      "rounds": 4
    }
  },
  "recordAfterCore": {
    "commentsInView": 4,
    "pendingAtPaint": true
  },
  "ages": [
    "186 min",
    "185 min",
    "4 min"
  ],
  "listedState": {
    "newerList": "Merged",
    "olderList": "Open"
  },
  "changes": {
    "settled": {
      "asked": 200,
      "held": true,
      "readyWhileHeld": false,
      "shown": true,
      "ready": true,
      "holdingAtJump": true
    },
    "bound": {
      "asked": 200,
      "held": true,
      "readyWhileHeld": false,
      "shown": true,
      "ready": true,
      "holdingAtJump": true
    },
    "cancelled": {
      "held": true,
      "keptOutOfSight": true,
      "outcome": "cancelled"
    }
  },
  "bounded": true,
  "tabKeysWhileHeld": {
    "whileHeld": {
      "holding": true,
      "tabColumn": "live",
      "live": [
        "conversation",
        "files",
        "checks"
      ],
      "badges": "Conversation C, Changes G, Checks E",
      "g": "opened the files route",
      "stackMenus": 1,
      "stackKeys": "pulls.stack.top, pulls.stack.base",
      "strip": "pulls.stack.top, pulls.stack.base",
      "control-n": "opened #8"
    },
    "released": {
      "holding": false,
      "tabColumn": "live",
      "live": [
        "conversation",
        "files",
        "checks"
      ],
      "badges": "Conversation C, Changes G, Checks E",
      "focus": "none",
      "g": "opened the files route",
      "stackMenus": 1,
      "stackKeys": "pulls.stack.top, pulls.stack.base",
      "strip": "pulls.stack.top, pulls.stack.base",
      "n": "not handled",
      "control-n": "opened #8",
      "control-p": "opened #6"
    }
  }
}
? 0
```
