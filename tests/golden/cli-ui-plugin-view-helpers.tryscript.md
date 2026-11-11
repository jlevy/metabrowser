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
The synchronous template helper uses real vendored Mustache for escaping and sections.
Its idle prefetch and plugin demand share one request; a held template response keeps
plugin code from running even when the other helpers have loaded.
When either required asset cannot be fetched, the load is refused, no plugin code has
run, and asking again fetches only what failed.

```console
$ node tests/dom/plugin-view-helpers-session.js
{
  "withoutACompositor": {
    "helpersBefore": "0 of 15",
    "requestedTogether": [
      "link rel=stylesheet /plugin-static/fixture-kind/styles.css",
      "link rel=modulepreload <the plugin's module>",
      "script /static/plugin-sdk-views.js",
      "script /static/vendor/mustache.min.js"
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
    "helpersAfter": "15 of 15",
    "pluginCode": [
      "module evaluation: a Source view with a gutter of 1 lines",
      "render: a Source view with a gutter of 2 lines",
      "click handler: a Source view with a gutter of 3 lines",
      "module evaluation: a Source view with a gutter of 1 lines"
    ],
    "templateCalls": [
      "module evaluation: <p>&lt;card&gt; &amp; text</p><b>one</b><b>&lt;two&gt;</b>",
      "render: <p>&lt;card&gt; &amp; text</p><b>one</b><b>&lt;two&gt;</b>",
      "click handler: <p>&lt;card&gt; &amp; text</p><b>one</b><b>&lt;two&gt;</b>",
      "module evaluation: <p>&lt;card&gt; &amp; text</p><b>one</b><b>&lt;two&gt;</b>"
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
  },
  "whenTemplatesCannotBeFetched": {
    "whileHeld": {
      "loading": "pending",
      "helpers": "15 of 15",
      "templateRequests": 1,
      "pluginCode": []
    },
    "afterFailure": {
      "loading": "rejected: Failed to load asset: /static/vendor/mustache.min.js",
      "prefetch": "rejected: Failed to load asset: /static/vendor/mustache.min.js",
      "pluginCode": [],
      "viewRegistered": false
    },
    "retry": {
      "requested": [
        "script /static/vendor/mustache.min.js"
      ],
      "loading": "resolved",
      "pluginCode": [
        "module evaluation: a Source view with a gutter of 1 lines"
      ],
      "templateCalls": [
        "module evaluation: <p>&lt;card&gt; &amp; text</p><b>one</b><b>&lt;two&gt;</b>"
      ]
    }
  },
  "sourceHeaderReadiness": {
    "folder": {
      "requested": [],
      "loading": "resolved"
    },
    "requestedTogether": [
      "source-ref-selector",
      "sdk-views"
    ],
    "afterSelector": {
      "loading": "pending",
      "mounted": []
    },
    "loaded": {
      "loading": "resolved",
      "mounted": [
        "source header"
      ]
    },
    "afterFailure": {
      "loading": "rejected: helpers unavailable",
      "mounted": []
    },
    "retry": {
      "loading": "resolved",
      "mounted": [
        "source header"
      ]
    }
  }
}
? 0
```
