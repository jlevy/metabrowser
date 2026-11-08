---
cwd: ../..
sandbox: false
---
# Golden Test for Quick Search

The production search controller and palette display file matches while a PR title
lookup is pending. The selected file stays selected when the PR arrives.
The result shows the title, number, and state and opens with Enter or a click.
A title query shows cached PRs while the catalog refreshes and keeps the selected PR as
more results arrive.
The result cap and the limit on how far back the title search looks have separate
notices.

A lone `#` shows recent cached PRs across states.
A title or number prefix after `#` searches PRs alone, and an exact PR number ranks
first among its prefix matches.
The selected PR survives when more prefix matches arrive.
Bare digits look up the exact PR alongside file matches.
In a plain folder, a hash remains part of the filename query.
File indexing leaves explicit PR searches alone and refreshes mixed results once they
settle. An obsolete response cannot replace a newer query.
A cold catalog starts one shared refresh and the standing query finds the result when it
reaches disk.

```console
$ node tests/dom/quick-search-pulls-session.js
{
  "heading": "Quick Search",
  "placeholder": "Search files or PRs. Type # for recent PRs.",
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
  "grown": [
    "render.js",
    "Pull request #124, Render the latest state, Closed",
    "src/renderer.js",
    "Pull request #123, Fix <em>renderer</em>, Merged"
  ],
  "selectedAfterGrowth": "Pull request #123, Fix <em>renderer</em>, Merged",
  "truncatedStatus": "2 matching files in 3 indexed files. Scanning continues. 2 pull requests shown. Showing the top matches.",
  "mixedKeptReading": true,
  "afterFileGrowth": [
    "render.js",
    "Pull request #124, Render the latest state, Closed",
    "src/renderer.js",
    "Pull request #123, Fix <em>renderer</em>, Merged",
    "z/render-guide.md",
    "z/render-notes.md"
  ],
  "selectedAfterFileGrowth": "Pull request #123, Fix <em>renderer</em>, Merged",
  "limitedStatus": "No matches in 5 indexed files. Scanning continues. No matching cached pull requests. Search by number for older pull requests.",
  "recents": [
    "Pull request #124, Render the latest state, Closed",
    "Pull request #123, Fix <em>renderer</em>, Merged"
  ],
  "prefix": [
    "Pull request #12, Exact number, Draft",
    "Pull request #124, Render the latest state, Closed",
    "Pull request #123, Fix <em>renderer</em>, Merged"
  ],
  "selectedAfterPrefixGrowth": "Pull request #123, Fix <em>renderer</em>, Merged",
  "explicitTitle": [
    "Pull request #124, Render the latest state, Closed",
    "Pull request #123, Fix <em>renderer</em>, Merged"
  ],
  "explicitTitleHighlight": "Render",
  "hashFiles": [
    "new/#render.md",
    "notes/#render.md"
  ],
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
  "exactKeptReading": true,
  "pullOpenFailure": "Could not open this pull request. Try again.",
  "requests": [
    "GET /api/plugin/github/pulls?q=render",
    "GET /api/plugin/github/pulls?q=render",
    "GET /api/plugin/github/pulls?q=render",
    "GET /api/plugin/github/pulls?q=older",
    "GET /api/plugin/github/pulls?q=%23",
    "GET /api/plugin/github/pulls?q=%23",
    "GET /api/plugin/github/pulls?q=%2312",
    "GET /api/plugin/github/pulls?q=%2312",
    "GET /api/plugin/github/pulls?q=%23render",
    "GET /api/plugin/github/pulls?q=%23123",
    "GET /api/plugin/github/pulls?q=123",
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
