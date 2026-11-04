---
cwd: ../..
sandbox: false
---
# Golden test: external GitHub destination marks

The production SDK helper preserves authored links and marks only recognized GitHub
hosts.
Canonical issue and pull request links have neutral entity marks until the calling
view has a matching record.
The PR page supplies actual state only for its own entity, after conversation HTML has
passed through the production inert sanitizer.
No lookup or remote image is needed.

```console
$ node tests/dom/external-links-session.js
{
  "destinations": [
    {
      "href": "https://github.com/octo/demo",
      "icon": "github"
    },
    {
      "href": "https://github.com/octo",
      "icon": "github"
    },
    {
      "href": "//github.com/octo/demo/pull/7",
      "icon": "pull"
    },
    {
      "href": "https://github.com/octo/demo/PULL/7",
      "icon": "github"
    },
    {
      "href": "https://www.github.com/octo/demo",
      "icon": "github"
    },
    {
      "href": "https://cli.github.com/",
      "icon": "github"
    },
    {
      "href": "https://docs.github.com/en",
      "icon": "github"
    },
    {
      "href": "https://gist.github.com/octo/abcd",
      "icon": "github"
    },
    {
      "href": "https://api.github.com/repos/octo/demo",
      "icon": "github"
    },
    {
      "href": "https://github.com/octo/demo/issues/7#comment",
      "icon": "issue"
    },
    {
      "href": "https://github.com/octo/demo/pull/7/files?x=1#L2",
      "icon": "pull"
    },
    {
      "href": "https://github.com/octo/demo/issues/0",
      "icon": "github"
    },
    {
      "href": "https://github.com/octo/demo/pull/no",
      "icon": "github"
    },
    {
      "href": "https://github.com/octo/demo/pull/7evil",
      "icon": "github"
    },
    {
      "href": "https://github.com/octo/demo/pull/%37",
      "icon": "github"
    },
    {
      "href": "https://example.com/check/7",
      "icon": null
    },
    {
      "href": "https://github.com.example.com/octo/demo/pull/7",
      "icon": null
    },
    {
      "href": "https://octo.github.io/",
      "icon": null
    },
    {
      "href": "https://github.com@evil.example/",
      "icon": null
    },
    {
      "href": "https://name@github.com/",
      "icon": null
    },
    {
      "href": "https://github.com:444/",
      "icon": null
    },
    {
      "href": "javascript:alert(1)",
      "icon": null
    },
    {
      "href": "/pull/7",
      "icon": null
    },
    {
      "href": "/view/docs/readme.md",
      "icon": null
    }
  ],
  "preserved": [
    "href",
    "target",
    "rel",
    "accessible name",
    "authored nodes"
  ],
  "updates": [
    "idempotent node",
    "trusted supplied state",
    "internal href removes owned icon",
    "authored forged marker retained without trust",
    "new destination reclassified"
  ],
  "providerCalls": 0,
  "sanitizedConversation": [
    {
      "href": "https://github.com/octo/demo/pull/7#issuecomment-1",
      "icon": "pull",
      "state": "merged"
    },
    {
      "href": "https://github.com/octo/demo/pull/7/files",
      "icon": "pull",
      "state": "merged"
    },
    {
      "href": "https://github.com/other/demo/pull/7",
      "icon": "pull",
      "state": null
    },
    {
      "href": "https://github.com/octo/demo/pull/8",
      "icon": "pull",
      "state": null
    },
    {
      "href": "https://github.com/octo/demo/issues/7",
      "icon": "issue",
      "state": null
    },
    {
      "href": "https://ci.example/check/7",
      "icon": null,
      "state": null
    }
  ],
  "knownStates": [
    "open",
    "draft",
    "closed",
    "merged"
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
