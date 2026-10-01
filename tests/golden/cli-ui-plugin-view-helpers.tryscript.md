---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: the SDK’s view helpers wherever a plugin’s code runs

`renderSourceView` and the other helpers that build a view’s markup, with the line
gutter they draw, are an on-demand bundle and not a startup script.
The shell fetches the bundle beside the view compositor.
A plugin loaded where no compositor ran, as the commit page loads the diff plugin and
the pull-request page loads its own, must still find every documented helper: while its
module evaluates, in a view’s render, and in a handler.

This session loads the production asset loader and plugin SDK from a command line and
loads a third-party plugin through `ensureKindAssets` with no compositor.
Every element the page appends to its head is a request the session answers when it
chooses. It pins that the helpers, the plugin’s stylesheet, and a preload of its module
are requested together, so the wait costs no round trip; that none of the plugin’s code
runs until the helpers are there; that a helper then works in all three places; and that
a second plugin asks only for its own assets.
When the bundle cannot be fetched, the load is refused, no plugin code has run, and
asking again fetches only what failed.

```console
$ node tests/dom/plugin-view-helpers-session.js
{
  "withoutACompositor": {
    "helpersBefore": "0 of 9",
    "requestedTogether": [
      "link rel=stylesheet /plugin-static/fixture-kind/styles.css",
      "link rel=modulepreload <the plugin's module>",
      "script /static/plugin-sdk-views.js"
    ],
    "whileWaiting": {
      "loading": "pending",
      "pluginCode": []
    },
    "loaded": {
      "loading": "resolved",
      "pluginCode": [
        "module evaluation: a Source view with a gutter of 1 lines"
      ]
    },
    "helpersAfter": "9 of 9",
    "pluginCode": [
      "module evaluation: a Source view with a gutter of 1 lines",
      "render: a Source view with a gutter of 2 lines",
      "click handler: a Source view with a gutter of 3 lines",
      "module evaluation: a Source view with a gutter of 1 lines"
    ],
    "aSecondPlugin": {
      "requested": [
        "link rel=stylesheet /plugin-static/another-kind/styles.css",
        "link rel=modulepreload <the plugin's module>"
      ],
      "loading": "resolved"
    }
  },
  "whenTheHelpersCannotBeFetched": {
    "afterFailure": {
      "loading": "rejected: Failed to load asset: /static/plugin-sdk-views.js",
      "pluginCode": [],
      "viewRegistered": false
    },
    "retry": {
      "requested": [
        "script /static/plugin-sdk-views.js"
      ],
      "loading": "resolved",
      "pluginCode": [
        "module evaluation: a Source view with a gutter of 1 lines"
      ]
    }
  }
}
? 0
```
