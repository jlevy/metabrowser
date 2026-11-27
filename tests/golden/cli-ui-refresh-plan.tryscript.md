---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Navigation’s One Refresh

The icon button at the top of the navigation, on every page and under every tab, is the
page’s one Refresh (docs/design-system.md, “Refresh, Retry, and Reload Page”). One press
refreshes every part of the page that can be read again, through the path each part
already had, in one order (`static/refresh-plan.js`): the parts on screen first, then
the parts behind other tabs, so a tab the reader turns to next is already fresh.
Within each half the order is the plan’s: the mirror’s fetch first, since every other
part reads what it brings, then the branch and tag chooser’s list, then the pull
request’s page in the main pane, then the tabs, Files, Pulls, and Commits, and last a
checkout’s working tree’s fetch of its origin.

What is on screen is read from the tab in front and from what holds the main pane: the
mirror’s freshness row is at the foot of the navigation on every tab; the pull request’s
page while it holds the pane; and a tab’s part while it is in front, or, for Files and
Commits, while the pane shows its file, folder, or commit.
The chooser’s list is on screen while it is open.
A working tree’s fetch of its origin never is, since nothing its page shows waits for
it: the page has no freshness row, so its press reads the disk and the history again and
only then, with the button offered again, asks for that fetch.

The button sets `aria-disabled` as soon as it accepts the press and keeps it while the
parts on screen refresh.
A quick press shows its spinner briefly, and a press while it waits does nothing.
A part that fails says so where it is drawn, and the rest still run.
A later press supersedes what an earlier one had not reached behind the other tabs.
The last steps run the module’s browser glue on a stand-in page, with the shell’s parts
as app.js, the freshness row, and the Commits panel lend them, and the Pulls list’s two
as pulls-panel.js does.
The chooser cases use a revision and a working tree, with the list open and closed.
The last case follows the tooltip across tabs and checks the spinner after a quick
refresh.

`tests/test_refresh_plan_session.py` holds the record to these invariants;
`cli-ui-key-reveal.tryscript.md` shows the button numbered 1 on every screen.

```console
$ node tests/dom/refresh-plan-session.js
{
  "steps": [
    {
      "step": "each screen's order: the parts on screen, then the rest, each half in plan order",
      "parts": [
        "source",
        "refs",
        "page",
        "files",
        "pulls",
        "git",
        "origin"
      ],
      "screens": [
        {
          "screen": "Files in front, a file in the pane",
          "visible": [
            "source",
            "files"
          ],
          "hidden": [
            "refs",
            "page",
            "pulls",
            "git",
            "origin"
          ]
        },
        {
          "screen": "Files in front, nothing chosen",
          "visible": [
            "source",
            "files"
          ],
          "hidden": [
            "refs",
            "page",
            "pulls",
            "git",
            "origin"
          ]
        },
        {
          "screen": "Files in front, a pull request still in the pane",
          "visible": [
            "source",
            "page",
            "files"
          ],
          "hidden": [
            "refs",
            "pulls",
            "git",
            "origin"
          ]
        },
        {
          "screen": "Pulls in front, a pull request in the pane",
          "visible": [
            "source",
            "page",
            "pulls"
          ],
          "hidden": [
            "refs",
            "files",
            "git",
            "origin"
          ]
        },
        {
          "screen": "Pulls in front, a file still in the pane",
          "visible": [
            "source",
            "files",
            "pulls"
          ],
          "hidden": [
            "refs",
            "page",
            "git",
            "origin"
          ]
        },
        {
          "screen": "Commits in front, a commit in the pane",
          "visible": [
            "source",
            "git"
          ],
          "hidden": [
            "refs",
            "page",
            "files",
            "pulls",
            "origin"
          ]
        },
        {
          "screen": "Commits in front, a file still in the pane",
          "visible": [
            "source",
            "files",
            "git"
          ],
          "hidden": [
            "refs",
            "page",
            "pulls",
            "origin"
          ]
        },
        {
          "screen": "Files in front, the chooser's list open",
          "visible": [
            "source",
            "refs",
            "files"
          ],
          "hidden": [
            "page",
            "pulls",
            "git",
            "origin"
          ]
        }
      ]
    },
    {
      "step": "a press runs the parts on screen while the button waits, then the rest",
      "events": [
        "waits",
        "source starts",
        "source settles",
        "page starts",
        "page settles",
        "pulls starts",
        "pulls settles",
        "offered",
        "refs starts",
        "refs settles",
        "files starts",
        "files settles",
        "git starts",
        "git settles",
        "origin starts",
        "origin settles"
      ],
      "a second press while it waits": false,
      "the first press": true,
      "waiting after": false
    },
    {
      "step": "a part that fails leaves the rest to run",
      "events": [
        "waits",
        "source starts",
        "source failed: source could not be read",
        "files starts",
        "files settles",
        "offered",
        "refs starts",
        "refs settles",
        "page starts",
        "page settles",
        "pulls starts",
        "pulls settles",
        "git starts",
        "git settles",
        "origin starts",
        "origin settles"
      ]
    },
    {
      "step": "a released part is not run, and a stale release keeps the newer refresh",
      "parts": "source, refs, files, git, origin",
      "events": [
        "waits",
        "source starts",
        "source settles",
        "files starts",
        "files settles",
        "offered",
        "refs starts",
        "refs settles",
        "git, provided again, starts",
        "git starts",
        "git settles",
        "origin starts",
        "origin settles"
      ]
    },
    {
      "step": "a press while the hidden parts run supersedes the rest of the first",
      "events": [
        "waits",
        "source starts",
        "source settles",
        "files starts",
        "files settles",
        "offered",
        "refs starts",
        "waits",
        "source starts",
        "refs settles",
        "source settles",
        "files starts",
        "files settles",
        "offered",
        "refs starts",
        "refs settles",
        "page starts",
        "page settles",
        "pulls starts",
        "pulls settles",
        "git starts",
        "git settles",
        "origin starts",
        "origin settles"
      ]
    },
    {
      "step": "a part the plan does not list is refused",
      "refused": "Unknown refresh part: tree"
    },
    {
      "step": "a click with pulls in front and the pane's owner \"pull-request\"",
      "parts": [
        "source",
        "page",
        "files",
        "pulls",
        "git"
      ],
      "asked": [
        "the button: aria-disabled=true",
        "source: the freshness row's refreshNow starts",
        "source: the freshness row's refreshNow settles",
        "page: the part the Pulls list lends for the page beside it starts",
        "page: the part the Pulls list lends for the page beside it settles",
        "pulls: the part the Pulls list lends for itself starts",
        "pulls: the part the Pulls list lends for itself settles",
        "the button: no aria-disabled",
        "files: the shell's rereadFiles starts",
        "files: the shell's rereadFiles settles",
        "git: the Commits panel's refresh starts",
        "git: the Commits panel's refresh settles"
      ]
    },
    {
      "step": "a click with files in front and the pane's owner \"file\"",
      "parts": [
        "source",
        "page",
        "files",
        "pulls",
        "git"
      ],
      "asked": [
        "the button: aria-disabled=true",
        "source: the freshness row's refreshNow starts",
        "source: the freshness row's refreshNow settles",
        "files: the shell's rereadFiles starts",
        "files: the shell's rereadFiles settles",
        "the button: no aria-disabled",
        "page: the part the Pulls list lends for the page beside it starts",
        "page: the part the Pulls list lends for the page beside it settles",
        "pulls: the part the Pulls list lends for itself starts",
        "pulls: the part the Pulls list lends for itself settles",
        "git: the Commits panel's refresh starts",
        "git: the Commits panel's refresh settles"
      ]
    },
    {
      "step": "a click with git in front and the pane's owner \"git\"",
      "parts": [
        "source",
        "page",
        "files",
        "pulls",
        "git"
      ],
      "asked": [
        "the button: aria-disabled=true",
        "source: the freshness row's refreshNow starts",
        "source: the freshness row's refreshNow settles",
        "git: the Commits panel's refresh starts",
        "git: the Commits panel's refresh settles",
        "the button: no aria-disabled",
        "page: the part the Pulls list lends for the page beside it starts",
        "page: the part the Pulls list lends for the page beside it settles",
        "files: the shell's rereadFiles starts",
        "files: the shell's rereadFiles settles",
        "pulls: the part the Pulls list lends for itself starts",
        "pulls: the part the Pulls list lends for itself settles"
      ]
    },
    {
      "step": "a click with files in front and the pane's owner \"file\", a local repository with no store and no Pulls tab",
      "parts": [
        "files",
        "git"
      ],
      "asked": [
        "the button: aria-disabled=true",
        "files: the shell's rereadFiles starts",
        "files: the shell's rereadFiles settles",
        "the button: no aria-disabled",
        "git: the Commits panel's refresh starts",
        "git: the Commits panel's refresh settles"
      ]
    },
    {
      "step": "a click with files in front and the pane's owner \"file\", after the freshness row's script failed to load once",
      "parts": [
        "source",
        "page",
        "files",
        "pulls",
        "git"
      ],
      "asked": [
        "the freshness row's script fails to load",
        "the console: Refresh could not start the freshness row",
        "the button: aria-disabled=true",
        "source: the freshness row's refreshNow starts",
        "source: the freshness row's refreshNow settles",
        "files: the shell's rereadFiles starts",
        "files: the shell's rereadFiles settles",
        "the button: no aria-disabled",
        "page: the part the Pulls list lends for the page beside it starts",
        "page: the part the Pulls list lends for the page beside it settles",
        "pulls: the part the Pulls list lends for itself starts",
        "pulls: the part the Pulls list lends for itself settles",
        "git: the Commits panel's refresh starts",
        "git: the Commits panel's refresh settles"
      ]
    },
    {
      "step": "a click with files in front and the pane's owner \"file\", a revision with the chooser's list open",
      "parts": [
        "source",
        "refs",
        "page",
        "files",
        "pulls",
        "git"
      ],
      "asked": [
        "the button: aria-disabled=true",
        "source: the freshness row's refreshNow starts",
        "source: the freshness row's refreshNow settles",
        "refs: the chooser's reread starts",
        "refs: the chooser's reread settles",
        "files: the shell's rereadFiles starts",
        "files: the shell's rereadFiles settles",
        "the button: no aria-disabled",
        "page: the part the Pulls list lends for the page beside it starts",
        "page: the part the Pulls list lends for the page beside it settles",
        "pulls: the part the Pulls list lends for itself starts",
        "pulls: the part the Pulls list lends for itself settles",
        "git: the Commits panel's refresh starts",
        "git: the Commits panel's refresh settles"
      ]
    },
    {
      "step": "a click with files in front and the pane's owner \"file\", a revision with the chooser's list closed",
      "parts": [
        "source",
        "refs",
        "page",
        "files",
        "pulls",
        "git"
      ],
      "asked": [
        "the button: aria-disabled=true",
        "source: the freshness row's refreshNow starts",
        "source: the freshness row's refreshNow settles",
        "files: the shell's rereadFiles starts",
        "files: the shell's rereadFiles settles",
        "the button: no aria-disabled",
        "refs: the chooser's reread starts",
        "refs: the chooser's reread settles",
        "page: the part the Pulls list lends for the page beside it starts",
        "page: the part the Pulls list lends for the page beside it settles",
        "pulls: the part the Pulls list lends for itself starts",
        "pulls: the part the Pulls list lends for itself settles",
        "git: the Commits panel's refresh starts",
        "git: the Commits panel's refresh settles"
      ]
    },
    {
      "step": "a click with files in front and the pane's owner \"file\", a checkout's working tree with the chooser's list open",
      "parts": [
        "refs",
        "files",
        "git",
        "origin"
      ],
      "asked": [
        "the button: aria-disabled=true",
        "refs: the chooser's reread starts",
        "refs: the chooser's reread settles",
        "files: the shell's rereadFiles starts",
        "files: the shell's rereadFiles settles",
        "the button: no aria-disabled",
        "git: the Commits panel's refresh starts",
        "git: the Commits panel's refresh settles",
        "origin: the chooser's fetchOrigin starts",
        "origin: the chooser's fetchOrigin settles"
      ]
    },
    {
      "step": "a click with git in front and the pane's owner \"git\", a checkout's working tree with the chooser's list closed",
      "parts": [
        "refs",
        "files",
        "git",
        "origin"
      ],
      "asked": [
        "the button: aria-disabled=true",
        "git: the Commits panel's refresh starts",
        "git: the Commits panel's refresh settles",
        "the button: no aria-disabled",
        "refs: the chooser's reread starts",
        "refs: the chooser's reread settles",
        "files: the shell's rereadFiles starts",
        "files: the shell's rereadFiles settles",
        "origin: the chooser's fetchOrigin starts",
        "origin: the chooser's fetchOrigin settles"
      ]
    },
    {
      "step": "the Refresh tooltip follows the tab and a quick press shows a spinner",
      "pullsHint": "Refreshed 2 min ago in 300ms",
      "spokenHint": "Refreshed 2 min ago in 300ms",
      "filesHint": "Refresh",
      "waitingForSource": true,
      "spinner": {
        "immediate": true,
        "briefly": true,
        "ended": true
      }
    }
  ]
}
? 0
```
