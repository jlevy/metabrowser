---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Fetch Changes Beside a Checkout

The production pull controller consumes the checkout route replies recorded by
`tests/test_cli_github_checkout_golden.py`. Opening Files changed starts no fetch.
The explicit Fetch changes action requests a comparison; polling then receives its store
route while the folder stays unpinned, with no Browse code or head-switch action.
A second click during the job sends nothing.

```console
$ node tests/dom/github-checkout-comparison-session.js
[
  {
    "step": "opening Files changed acquires nothing",
    "requests": [
      {
        "method": "GET",
        "route": "/api/plugin/github/pull?number=10"
      }
    ],
    "canFetchChanges": true,
    "refreshing": false,
    "comparison": null,
    "browse": null,
    "headOffer": null
  },
  {
    "step": "Fetch changes starts the explicit comparison job",
    "requests": [
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
    "canFetchChanges": false,
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
    "canFetchChanges": false,
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

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
