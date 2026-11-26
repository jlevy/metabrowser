---
cwd: ../..
sandbox: false
---
# Golden Test for Quick Search

The production search controller and palette display file matches while a PR title
lookup is pending. Pull requests are their own group after the files, so the PR that
arrives later is appended below them and the selected file stays where it was.
The result shows the title, number, and state and opens with Enter or a click.
A title query shows cached PRs while the catalog refreshes and keeps the selected PR as
more results arrive.
The result cap and the limit on how far back the title search looks have separate
notices.

A lone `#` shows recent cached PRs across states.
A title or number prefix after `#` searches PRs alone, and an exact PR number ranks
first among its prefix matches.
The selected PR survives when more prefix matches arrive.
A title that starts with a conventional-commit prefix is drawn in two parts, the prefix
in its `span.title-prefix`, and a word the query matches in both parts is marked in
each, at its own place.
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
    "src/renderer.js",
    "Fix <em>renderer</em>, pull request #123, Merged"
  ],
  "afterMerge": "src/renderer.js",
  "titleHighlight": "render",
  "details": "#123 · Merged",
  "grown": [
    "render.js",
    "src/renderer.js",
    "Render the latest state, pull request #124, Closed",
    "Fix <em>renderer</em>, pull request #123, Merged"
  ],
  "selectedAfterGrowth": "Fix <em>renderer</em>, pull request #123, Merged",
  "truncatedStatus": "2 matching files in 3 indexed files. Scanning continues. 2 pull requests shown. Showing the top matches.",
  "mixedKeptReading": true,
  "afterFileGrowth": [
    "render.js",
    "src/renderer.js",
    "z/render-guide.md",
    "z/render-notes.md",
    "Render the latest state, pull request #124, Closed",
    "Fix <em>renderer</em>, pull request #123, Merged"
  ],
  "selectedAfterFileGrowth": "Fix <em>renderer</em>, pull request #123, Merged",
  "limitedStatus": "No matches in 5 indexed files. Scanning continues. No matching pull requests. Search by number for older pull requests.",
  "recents": [
    "Render the latest state, pull request #124, Closed",
    "Fix <em>renderer</em>, pull request #123, Merged"
  ],
  "prefix": [
    "Exact number, pull request #12, Draft",
    "Render the latest state, pull request #124, Closed",
    "Fix <em>renderer</em>, pull request #123, Merged"
  ],
  "selectedAfterPrefixGrowth": "Fix <em>renderer</em>, pull request #123, Merged",
  "explicitTitle": [
    "Render the latest state, pull request #124, Closed",
    "Fix <em>renderer</em>, pull request #123, Merged"
  ],
  "explicitTitleHighlight": "Render",
  "prefixedChoices": [
    "feat(chart): chart the strategies, pull request #125, Open"
  ],
  "prefixedTitle": [
    {
      "span.title-prefix": [
        "feat(",
        {
          "mark": "chart"
        },
        "):"
      ]
    },
    " ",
    {
      "mark": "chart"
    },
    " the strategies"
  ],
  "hashFiles": [
    "new/#render.md",
    "notes/#render.md"
  ],
  "exact": [
    "Fix <em>renderer</em>, pull request #123, Merged"
  ],
  "staleRequestAborted": true,
  "bare": [
    "notes/123.md",
    "Fix <em>renderer</em>, pull request #123, Merged"
  ],
  "opened": [
    123,
    123
  ],
  "cold": [
    "Cold catalog match, pull request #77, Open"
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
    "GET /api/plugin/github/pulls?q=%23chart",
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
