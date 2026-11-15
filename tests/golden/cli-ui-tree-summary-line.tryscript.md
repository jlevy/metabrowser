---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Files Totals Line

The line under the Files toolbar states the served root’s totals.
It is a navigation metadata line, `.nav-metadata`, the component the Commits tally and
the Pulls count share (`docs/design-system.md`, “Navigation Metadata Line”), and its
markup and words are `treeSummaryHtml` in `static/navigation.js`, written with the
shell’s own text helpers.

This browserless session runs the real `static/navigation.js` with `esc`, `formatCount`,
and `formatSize` extracted verbatim from `static/app.js`, the helpers the shell hands
it. For each state the line paints in, it records the line’s classes, how it reads, how
many figures are still pending, and its markup.
`live` records the two figures the shell patches as the walker’s root aggregate changes.
The transcript pins these behaviors:

- Every state is a `.nav-metadata` line; none uses the tree rows’ count or size chips.
- Before any count, both figures are the pending tally, where the figures will be.
- The fallback, before the split arrives, says the figure in the split’s own words, “N
  files (size)”, so the line reads the same when the split replaces it.
- A Git pin has no size fact, so its line states none.
- The split adds the gitignored half only when there is one.

```console
$ node tests/dom/tree-summary-line-session.js
{
  "states": {
    "first paint, before any count": {
      "classes": "tree-summary nav-metadata",
      "reads": "",
      "pending": 2,
      "html": "<div class=\"tree-summary nav-metadata\"><span class=\"tree-summary-count\"><span class=\"count tally-pending\"></span></span><span class=\"tree-summary-size\"><span class=\"size tally-pending\"></span></span></div>"
    },
    "counted, before the split arrives": {
      "classes": "tree-summary nav-metadata",
      "reads": "12,797 files (394.6 MB)",
      "pending": 0,
      "html": "<div class=\"tree-summary nav-metadata\"><span class=\"tree-summary-count\">12,797 files</span><span class=\"tree-summary-size\">(394.6 MB)</span></div>"
    },
    "a Git pin, which has no sizes": {
      "classes": "tree-summary nav-metadata",
      "reads": "4 files",
      "pending": 0,
      "html": "<div class=\"tree-summary nav-metadata\"><span class=\"tree-summary-count\">4 files</span><span class=\"tree-summary-size\"></span></div>"
    },
    "the split, nothing ignored": {
      "classes": "tree-summary tree-summary-split nav-metadata",
      "reads": "4 files (38 B)",
      "pending": 0,
      "html": "<div class=\"tree-summary tree-summary-split nav-metadata\"><span class=\"tree-summary-tracked\">4 files</span><span class=\"tree-summary-bytes\">(38 B)</span></div>"
    },
    "the split, with ignored files": {
      "classes": "tree-summary tree-summary-split nav-metadata",
      "reads": "12,797 files (394.6 MB) + 248,189 ignored (9632.1 MB)",
      "pending": 0,
      "html": "<div class=\"tree-summary tree-summary-split nav-metadata\"><span class=\"tree-summary-tracked\">12,797 files</span><span class=\"tree-summary-bytes\">(394.6 MB)</span><span class=\"tree-summary-ignored\"><span class=\"tree-summary-plus\">+</span>248,189 ignored<span class=\"tree-summary-bytes\">(9632.1 MB)</span></span></div>"
    },
    "an empty folder": {
      "classes": "tree-summary tree-summary-split nav-metadata",
      "reads": "0 files (0 B)",
      "pending": 0,
      "html": "<div class=\"tree-summary tree-summary-split nav-metadata\"><span class=\"tree-summary-tracked\">0 files</span><span class=\"tree-summary-bytes\">(0 B)</span></div>"
    },
    "one file": {
      "classes": "tree-summary tree-summary-split nav-metadata",
      "reads": "1 file (2.0 KB)",
      "pending": 0,
      "html": "<div class=\"tree-summary tree-summary-split nav-metadata\"><span class=\"tree-summary-tracked\">1 file</span><span class=\"tree-summary-bytes\">(2.0 KB)</span></div>"
    }
  },
  "live": {
    "count still being counted": "<span class=\"count tally-pending\"></span>",
    "count known": "1 file",
    "count omitted": "",
    "size still being counted": "<span class=\"size tally-pending\"></span>",
    "size known": "(1.5 KB)",
    "size omitted": ""
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
