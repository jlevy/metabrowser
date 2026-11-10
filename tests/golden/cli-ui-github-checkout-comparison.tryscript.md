---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Fetch Changes Beside a Checkout

The production pull controller consumes the checkout route replies recorded by
`tests/test_cli_github_checkout_golden.py`. Conversation reads metadata and a visible
Changes tab starts a comparison automatically.
Polling receives its store route while the folder stays unpinned, with no Browse code or
head-switch action. Leaving and returning to Changes during the job sends no duplicate
request.

```console
$ node tests/dom/github-checkout-comparison-session.js
[
  {
    "step": "Conversation reads without acquiring a comparison",
    "requests": [
      {
        "method": "GET",
        "route": "/api/plugin/github/pull?number=10"
      }
    ],
    "changesPending": false,
    "canRetryChanges": false,
    "refreshing": false,
    "comparison": null,
    "browse": null,
    "headOffer": null
  },
  {
    "step": "visible Changes starts the comparison automatically",
    "requests": [
      {
        "method": "GET",
        "route": "/api/plugin/github/pull?number=10"
      },
      {
        "method": "POST",
        "route": "/api/plugin/github/pull-refresh",
        "body": {
          "number": 10,
          "retry": true,
          "comparison": true
        }
      }
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "refreshing": true,
    "comparison": null,
    "browse": null,
    "headOffer": null
  },
  {
    "step": "the finished comparison stays beside the folder",
    "requests": [
      {
        "method": "GET",
        "route": "/api/plugin/github/pull?number=10"
      }
    ],
    "changesPending": false,
    "canRetryChanges": false,
    "refreshing": false,
    "comparison": {
      "left": "c691256511d05858850bc7684ae062fea0d41132",
      "right": "7a7d6596e515735d244dc1d942463c95851e139c",
      "route": "/api/plugin/github/pull-comparison?number=10&left=c691256511d05858850bc7684ae062fea0d41132&right=7a7d6596e515735d244dc1d942463c95851e139c&base_policy=merge_base&build=<BUILD>&store=<STORE_TAG>",
      "headMoved": false
    },
    "browse": null,
    "headOffer": null
  }
]
? 0
```

An idle, visible Conversation can prepare the comparison from its cached record.
A reader opening Changes promotes that job.
An idle refusal leaves Changes free to start its own request.

```console
$ node tests/dom/github-pull-idle-comparison-behavior.js
{"changesBeforeIdle":["foreground"],"hiddenUntilVisible":["idle","foreground"],"afterLateIdleReply":"Changes ready","afterIdleRefusal":["idle","foreground"],"disposed":[]}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
