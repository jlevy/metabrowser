---
cwd: ../..
sandbox: false
---
# Golden Test for Quick Search

The production search controller and palette display file matches while a PR title
lookup is pending. The selected file stays selected when the PR arrives.
The result shows the title, number, and state and opens with Enter or a click.

A hash number searches PRs alone.
Bare digits include file matches too.
An obsolete response cannot replace a newer query.
A cold catalog starts one shared refresh and the standing query finds the result when it
reaches disk.

```console
$ node tests/dom/quick-search-pulls-session.js
{
  "heading": "Quick Search",
  "placeholder": "Type a file name, path, PR title, or #number",
  "firstPaint": [
    "render.js",
    "src/renderer.js"
  ],
  "mixed": [
    "render.js",
    "Pull request #123, Fix <em>renderer</em>, Merged",
    "src/renderer.js"
  ],
  "afterMerge": "src/renderer.js",
  "titleHighlight": "render",
  "details": "#123 · Merged",
  "exact": [
    "Pull request #123, Fix <em>renderer</em>, Merged"
  ],
  "staleRequestAborted": true,
  "bare": [
    "notes/123.md",
    "Pull request #123, Fix <em>renderer</em>, Merged"
  ],
  "opened": [
    123,
    123
  ],
  "cold": [
    "Pull request #77, Cold catalog match, Open"
  ],
  "pullOpenFailure": "Could not open this pull request. Try again.",
  "requests": [
    "GET /api/plugin/github/pulls?q=render",
    "GET /api/plugin/github/pulls?q=obsolete",
    "GET /api/plugin/github/pulls?q=%23123",
    "GET /api/plugin/github/pulls?q=%23123",
    "GET /api/plugin/github/pulls?q=%2377",
    "POST /api/plugin/github/pulls-refresh",
    "GET /api/plugin/github/pulls?q=%2377",
    "GET /api/plugin/github/pulls?q=%2377",
    "GET /api/plugin/github/pulls?q=%2377",
    "GET /api/plugin/github/pulls?q=%23999",
    "GET /api/plugin/github/pulls?q=%23998",
    "POST /api/plugin/github/pulls-refresh"
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
