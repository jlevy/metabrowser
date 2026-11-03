---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Files Changed Fetched From Conversation

The pull-request page knows the comparison the moment its record arrives, and a reader
on Conversation usually asks for Files changed next, so the page fetches it when the
browser is idle and hands it to the diff when the tab is clicked.
This browserless session runs the production
`builtin_plugins/github/comparison-prefetch.js` as the page does: `want` on each paint
of Conversation, `take` when a diff mounts, and `dispose` when the page goes.

Each step prints what has been asked of the server, what is held, and what a mount is
handed. A mount handed nothing asks for itself and reports its own errors.
The session asserts, and so prints nothing for, that a poll of the same record sends
nothing, that a mount waiting through a dispose is let go, and that a disposed prefetch
does nothing.

```console
$ node tests/dom/github-pull-prefetch-session.js
{
  "steps": [
    {
      "step": "the record names a comparison: nothing is sent until the browser is idle",
      "phase": "waiting",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [],
      "assetsWarmed": 0
    },
    {
      "step": "idle: one request, and the diff's assets",
      "phase": "fetching",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1
    },
    {
      "step": "the answer arrives and is held",
      "phase": "held",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1
    },
    {
      "step": "the reader clicks Files changed: it is handed over",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "handed": {
        "document": "first"
      }
    },
    {
      "step": "a later mount gets nothing here, and the browser's cache answers it",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "handed": null
    },
    {
      "step": "back on Conversation: nothing more is sent for that comparison",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1
    },
    {
      "step": "a click while the request is on its way waits for that request",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1
    },
    {
      "step": "it arrives",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "handed": {
        "document": "first"
      }
    },
    {
      "step": "a click before the browser was idle: the diff asks for itself, and only once",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [],
      "assetsWarmed": 0,
      "handed": null
    },
    {
      "step": "a page opened on Files changed sends nothing here",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [],
      "assetsWarmed": 0,
      "handed": null
    },
    {
      "step": "a refreshed record moved the head: the old request is cancelled",
      "phase": "waiting",
      "comparison": "aaaa...cccc",
      "holding": false,
      "requests": [
        "bbbb (cancelled)"
      ],
      "assetsWarmed": 1
    },
    {
      "step": "the new comparison is fetched",
      "phase": "fetching",
      "comparison": "aaaa...cccc",
      "holding": true,
      "requests": [
        "bbbb (cancelled)",
        "cccc"
      ],
      "assetsWarmed": 2
    },
    {
      "step": "a mount is waiting on the old request: it is not cancelled",
      "phase": "waiting",
      "comparison": "aaaa...cccc",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1
    },
    {
      "step": "a refused request is not retried and not an error: the diff asks and says why",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "handed": null
    },
    {
      "step": "a tab in the background sends nothing",
      "phase": "none",
      "comparison": null,
      "holding": false,
      "requests": [],
      "assetsWarmed": 0
    },
    {
      "step": "the same page once it is shown",
      "phase": "fetching",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1
    },
    {
      "step": "the page goes: its request is cancelled and nothing is held",
      "phase": "none",
      "comparison": null,
      "holding": false,
      "requests": [
        "bbbb (cancelled)"
      ],
      "assetsWarmed": 1
    },
    {
      "step": "the same endpoints at a changed route fetch again",
      "phase": "fetching",
      "comparison": "/api/plugin/github/pull-comparison?store=new",
      "holding": true,
      "requests": [
        "bbbb (cancelled)",
        "bbbb"
      ],
      "assetsWarmed": 2
    }
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
