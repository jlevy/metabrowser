---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Comparison Read Before Changes Asks

The pull-request page knows the comparison the moment its record arrives.
Its header’s Diff summary is drawn from it on every tab, and a reader on Conversation
often asks for Changes next.
So on every tab but Changes the prefetch reads it when the browser is idle, tells the
page what it read, and hands it to the diff when the tab is clicked.
This browserless session runs the production
`builtin_plugins/github/comparison-prefetch.js` as the page does: `want` on each paint
of every tab but Changes, `take` when a diff mounts, and `dispose` when the page goes.

Each step prints what has been asked of the server, what is held, and what a mount is
handed. A mount handed nothing asks for itself and reports its own errors.
A read that failed is told to the page, so its summary does not stand for another
comparison, and is asked for again at the next paint.
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
      "assetsWarmed": 0,
      "summarized": []
    },
    {
      "step": "idle: one request, and the diff's assets",
      "phase": "fetching",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": []
    },
    {
      "step": "the answer arrives and is held",
      "phase": "held",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ]
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
      "summarized": [
        "bbbb"
      ],
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
      "summarized": [
        "bbbb"
      ],
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
      "assetsWarmed": 1,
      "summarized": [
        "bbbb"
      ]
    },
    {
      "step": "a click while the request is on its way waits for that request",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": []
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
      "summarized": [
        "bbbb"
      ],
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
      "summarized": [],
      "handed": null
    },
    {
      "step": "a page opened on Files changed sends nothing here",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [],
      "assetsWarmed": 0,
      "summarized": [],
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
      "assetsWarmed": 1,
      "summarized": []
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
      "assetsWarmed": 2,
      "summarized": []
    },
    {
      "step": "a mount is waiting on the old request: it is not cancelled",
      "phase": "waiting",
      "comparison": "aaaa...cccc",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": []
    },
    {
      "step": "a refused request is not an error: the page is told, and the diff asks and says why",
      "phase": "taken",
      "comparison": "aaaa...bbbb",
      "holding": false,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": [],
      "handed": null,
      "failed": [
        "bbbb"
      ]
    },
    {
      "step": "a refused request is asked again at the page's next paint",
      "phase": "held",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [
        "bbbb",
        "bbbb"
      ],
      "assetsWarmed": 2,
      "summarized": [
        "bbbb"
      ],
      "failed": [
        "bbbb"
      ]
    },
    {
      "step": "a tab in the background sends nothing",
      "phase": "none",
      "comparison": null,
      "holding": false,
      "requests": [],
      "assetsWarmed": 0,
      "summarized": []
    },
    {
      "step": "the same page once it is shown",
      "phase": "fetching",
      "comparison": "aaaa...bbbb",
      "holding": true,
      "requests": [
        "bbbb"
      ],
      "assetsWarmed": 1,
      "summarized": []
    },
    {
      "step": "the page goes: its request is cancelled and nothing is held",
      "phase": "none",
      "comparison": null,
      "holding": false,
      "requests": [
        "bbbb (cancelled)"
      ],
      "assetsWarmed": 1,
      "summarized": []
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
      "assetsWarmed": 2,
      "summarized": []
    }
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
