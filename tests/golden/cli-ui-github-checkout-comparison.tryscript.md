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
Polling receives its store route while the folder stays unpinned; the session asserts
that there is no Browse code or head-switch action.
Leaving and returning to Changes during the job sends no duplicate request.

Changes shows progress only while an attempt is on its way or will be sent.
A direct cold visit asks for the pull request first and then for exactly one comparison.
When the server refuses that first request, nothing spins and the header offers Refresh.
Changes painted while the address still names Conversation sends nothing and offers
**Fetch**. A failed read before any attempt waits for the next good one.
A refused comparison offers **Retry** and keeps its reason across reads, said in the
Changes body beside it and not on the header, so no tab’s header differs, and a retry
that then fails shows its own outcome.
A refused Refresh is the header’s, even in the words a comparison’s refusal used: the
ask that met it tells them apart.
A recorded borrowing refusal or unreadable origin newer than the record, or a rate limit
until it lifts, holds the automatic attempt for **Retry**; an older failure does not.
The page wakes when the limit lifts, also when a Pulls-tab walk opened Changes and the
route then confirmed it, and **Retry** sends the attempt at once.
Changes opened while the page’s own refresh is on its way waits for it and paints no
button. A reader’s selection shows progress before its first read.

```console
$ node tests/dom/github-checkout-comparison-session.js
[
  {
    "step": "Conversation reads without acquiring a comparison",
    "requests": [
      "GET /api/plugin/github/pull?number=10"
    ],
    "changesPending": false,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": true,
    "files": null,
    "message": null,
    "failure": null,
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "visible Changes starts the comparison automatically",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Fetching changes…",
    "message": null,
    "failure": null,
    "refreshing": true,
    "comparison": null
  },
  {
    "step": "the finished comparison stays beside the folder",
    "requests": [
      "GET /api/plugin/github/pull?number=10"
    ],
    "changesPending": false,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": true,
    "files": null,
    "message": null,
    "failure": null,
    "refreshing": false,
    "comparison": {
      "left": "c691256511d05858850bc7684ae062fea0d41132",
      "right": "7a7d6596e515735d244dc1d942463c95851e139c",
      "route": "/api/plugin/github/pull-comparison?number=10&left=c691256511d05858850bc7684ae062fea0d41132&right=7a7d6596e515735d244dc1d942463c95851e139c&base_policy=merge_base&build=<BUILD>&store=<STORE_TAG>",
      "image_route": "/api/plugin/github/pull-image?number=10&left=c691256511d05858850bc7684ae062fea0d41132&right=7a7d6596e515735d244dc1d942463c95851e139c&store=<STORE_TAG>",
      "rendered_route": "/api/plugin/github/pull-rendered-diff?number=10&left=c691256511d05858850bc7684ae062fea0d41132&right=7a7d6596e515735d244dc1d942463c95851e139c&store=<STORE_TAG>",
      "size_route": "/api/plugin/github/pull-size?number=10&left=c691256511d05858850bc7684ae062fea0d41132&right=7a7d6596e515735d244dc1d942463c95851e139c&store=<STORE_TAG>",
      "branch": {
        "ref": "refs/pull/10/head"
      }
    }
  },
  {
    "step": "a cold direct Changes visit asks for the pull request first",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"wait_core\":true}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Changes are still being prepared.",
    "message": null,
    "failure": null,
    "refreshing": true,
    "comparison": null
  },
  {
    "step": "the record without a store starts one comparison",
    "requests": [
      "GET /api/plugin/github/pull?number=10&wait_full_after=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Fetching changes…",
    "message": null,
    "failure": null,
    "refreshing": true,
    "comparison": null
  },
  {
    "step": "a refused cold fetch stops showing progress",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"wait_core\":true}"
    ],
    "changesPending": false,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": true,
    "files": "Changes are unavailable because the full pull request could not be loaded.",
    "message": "The refresh could not start while other pull requests are being fetched.",
    "failure": null,
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "a later read neither spins nor asks again",
    "requests": [
      "GET /api/plugin/github/pull?number=10"
    ],
    "changesPending": false,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": true,
    "files": "Changes are unavailable because the full pull request could not be loaded.",
    "message": null,
    "failure": null,
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "Changes without its address waits for the reader",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "GET /api/plugin/github/pull?number=10"
    ],
    "changesPending": false,
    "canRetryChanges": false,
    "canFetchChanges": true,
    "canRefresh": false,
    "files": "Changes have not been fetched.",
    "message": null,
    "failure": null,
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "Changes' Fetch asks for the comparison",
    "requests": [
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Fetching changes…",
    "message": null,
    "failure": null,
    "refreshing": true,
    "comparison": null
  },
  {
    "step": "a failed read before any attempt waits without a retry",
    "requests": [
      "GET /api/plugin/github/pull?number=10"
    ],
    "changesPending": false,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Changes have not been fetched.",
    "message": "The pull request could not be loaded.",
    "failure": null,
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "the next good read starts the automatic attempt",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Fetching changes…",
    "message": null,
    "failure": null,
    "refreshing": true,
    "comparison": null
  },
  {
    "step": "a refused automatic comparison offers Changes' Retry",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": false,
    "canRetryChanges": true,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Changes could not be fetched. The refresh could not start while other pull requests are being fetched.",
    "message": null,
    "failure": null,
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "the refusal's reason stays after the next read",
    "requests": [
      "GET /api/plugin/github/pull?number=10"
    ],
    "changesPending": false,
    "canRetryChanges": true,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Changes could not be fetched. The refresh could not start while other pull requests are being fetched.",
    "message": null,
    "failure": null,
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "Changes' Retry asks again and clears the reason",
    "requests": [
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Fetching changes…",
    "message": null,
    "failure": null,
    "refreshing": true,
    "comparison": null
  },
  {
    "step": "a retry that fails shows its own outcome, not the earlier refusal",
    "requests": [
      "GET /api/plugin/github/pull?number=10"
    ],
    "changesPending": false,
    "canRetryChanges": true,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Changes could not be fetched.",
    "message": null,
    "failure": "The checkout cannot supply these changes.",
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "a refused comparison beside a failed refresh is said on Changes",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": false,
    "canRetryChanges": true,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Changes could not be fetched. The refresh could not start while other pull requests are being fetched.",
    "message": null,
    "failure": "Could not reach GitHub.",
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "a refused Refresh in the same words is said on the header",
    "requests": [
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true}"
    ],
    "changesPending": false,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": true,
    "files": null,
    "message": "The refresh could not start while other pull requests are being fetched.",
    "failure": "Could not reach GitHub.",
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "a recorded borrowing refusal holds the automatic attempt",
    "requests": [
      "GET /api/plugin/github/pull?number=10"
    ],
    "changesPending": false,
    "canRetryChanges": true,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Changes could not be fetched.",
    "message": null,
    "failure": "The checkout cannot supply these changes.",
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "an unreadable origin holds the automatic attempt too",
    "requests": [
      "GET /api/plugin/github/pull?number=10"
    ],
    "changesPending": false,
    "canRetryChanges": true,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Changes could not be fetched.",
    "message": null,
    "failure": "GitHub could not find this pull request, or this account cannot read it.",
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "a borrowing refusal older than the record does not hold",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Fetching changes…",
    "message": null,
    "failure": null,
    "refreshing": true,
    "comparison": null
  },
  {
    "step": "a rate limit holds the automatic attempt until it lifts",
    "requests": [
      "GET /api/plugin/github/pull?number=10"
    ],
    "changesPending": false,
    "canRetryChanges": true,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Changes could not be fetched.",
    "message": null,
    "failure": "GitHub rate limit reached. Next attempt after 12:05 PM.",
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "Changes' Retry after the limit lifts sends the attempt at once",
    "requests": [
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Fetching changes…",
    "message": null,
    "failure": null,
    "refreshing": true,
    "comparison": null
  },
  {
    "step": "the page wakes when the limit lifts and asks then",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Fetching changes…",
    "message": null,
    "failure": null,
    "refreshing": true,
    "comparison": null
  },
  {
    "step": "a walk's Changes wakes when the limit lifts and asks then",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Fetching changes…",
    "message": null,
    "failure": null,
    "refreshing": true,
    "comparison": null
  },
  {
    "step": "Changes opened during the page's own refresh waits for it",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"held\":\"641c13ea31b757850edb1a7975ac1051b58a9e221bb96e4d9e3451fd7b8d8c45\"}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Fetching changes…",
    "message": null,
    "failure": null,
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "the comparison follows the refresh's answer",
    "requests": [
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"retry\":true,\"comparison\":true}"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Fetching changes…",
    "message": null,
    "failure": null,
    "refreshing": true,
    "comparison": null
  },
  {
    "step": "Changes without its address paints no Fetch during the page's own refresh",
    "requests": [
      "GET /api/plugin/github/pull?number=10",
      "POST /api/plugin/github/pull-refresh {\"number\":10,\"held\":\"641c13ea31b757850edb1a7975ac1051b58a9e221bb96e4d9e3451fd7b8d8c45\"}"
    ],
    "changesPending": false,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": false,
    "files": "Changes have not been fetched.",
    "message": null,
    "failure": null,
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "Changes' Fetch returns with the refresh's answer",
    "requests": [],
    "changesPending": false,
    "canRetryChanges": false,
    "canFetchChanges": true,
    "canRefresh": false,
    "files": "Changes have not been fetched.",
    "message": null,
    "failure": null,
    "refreshing": false,
    "comparison": null
  },
  {
    "step": "a reader's selection shows progress before its first read",
    "requests": [
      "GET /api/plugin/github/pull?number=10"
    ],
    "changesPending": true,
    "canRetryChanges": false,
    "canFetchChanges": false,
    "canRefresh": true,
    "files": "Changes are still being prepared.",
    "message": null,
    "failure": null,
    "refreshing": false,
    "comparison": null
  }
]
? 0
```

An idle, visible Conversation can prepare the comparison from its cached record, but
only where the checkout already has a store; one with no store is never asked.
The page polls that optional job slowly, and a reader opening Changes promotes it.
An idle refusal leaves Changes free to start its own request.

```console
$ node tests/dom/github-pull-idle-comparison-behavior.js
{"withoutStore":[],"changesBeforeIdle":["foreground"],"pollWhilePreparing":{"conversation":30000,"changes":1000},"hiddenUntilVisible":["idle","foreground"],"afterLateIdleReply":"Changes ready","afterIdleRefusal":["idle","foreground"],"disposed":[]}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
