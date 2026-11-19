---
cwd: ../..
sandbox: false
---
# Guided PR step navigation

The production navigation waits for the cached PR, requests the selected step, and
discards late responses after a revision change or disposal.
An edited guide with fewer steps returns the reviewer to its first step.

```console
$ node tests/dom/github-guided-pr-session.js
{
  "calls": [
    1,
    2,
    1,
    1,
    2,
    2,
    1,
    1,
    1
  ],
  "states": [
    "preview",
    "loading",
    "step 1 of 2",
    "loading",
    "step 2 of 2",
    "loading",
    "stale",
    "loading",
    "step 1 of 2",
    "loading",
    "step 2 of 2",
    "loading",
    "step 1 of 1",
    "loading",
    "updated",
    "loading"
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
