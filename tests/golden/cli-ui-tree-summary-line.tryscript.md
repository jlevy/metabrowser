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

This browserless session runs the real `static/navigation.js` with `formatCountParts`
and `formatSize` extracted verbatim from `static/app.js`, the helpers the shell hands
it, over the real `static/formatters.js`, whose `formatBytes` writes every size the
shell shows and whose `countPartsHtml` paints every count summary’s numbers bold.
For each state the line paints in, it records the line’s classes, how it reads, how many
figures are still pending, the figures it paints bold (`numbers`), what it says in the
line’s own weight (`regular`), and its markup.
`live` records the two figures the shell patches as the walker’s root aggregate changes.
The transcript pins these behaviors:

- Every state is a `.nav-metadata` line; none uses the tree rows’ count or size chips.
- Before any count, both figures are the pending tally, where the figures will be.
- The fallback, before the split arrives, says the figure in the split’s own words, “N
  files (size)”, so the line reads the same when the split replaces it.
- A Git pin has no size fact, so its line states none.
- The split adds the gitignored half only when there is one, as a line of its own
  (`.tree-summary-ignored`).
- A line drawn before the root’s totals are known, asked to hold the ignored line, holds
  it with the pending placeholder after the quiet period, a status named for a screen
  reader; no other state holds one.
- `totals` records what the root’s own entry says: a root the walk has finished gives
  its tracked and ignored files and bytes, in the server’s `summary` shape, and a root
  still being walked, or a Git revision’s, which keeps no ignored totals, gives none.
- `sequence` records the held line as those totals arrive: it becomes the ignored count,
  or, with nothing ignored, goes away.
- Every figure, a count or a size with its unit, is a bold number, `.summary-number`,
  and the words and parentheses keep the line’s weight (`docs/design-system.md`, “Count
  Summaries Bold Their Numbers”).

```console
$ node tests/dom/tree-summary-line-session.js
{
  "states": {
    "first paint, before any count": {
      "classes": "tree-summary nav-metadata",
      "reads": "",
      "pending": 2,
      "ignoredLine": "none",
      "numbers": [],
      "regular": "",
      "html": "<div class=\"tree-summary nav-metadata\"><span class=\"tree-summary-count\"><span class=\"count tally-pending\"></span></span><span class=\"tree-summary-size\"><span class=\"size tally-pending\"></span></span></div>"
    },
    "counted, before the split arrives": {
      "classes": "tree-summary nav-metadata",
      "reads": "12,797 files (394.6 MB)",
      "pending": 0,
      "ignoredLine": "none",
      "numbers": [
        "12,797",
        "394.6 MB"
      ],
      "regular": "files ( )",
      "html": "<div class=\"tree-summary nav-metadata\"><span class=\"tree-summary-count\"><span class=\"summary-number\">12,797</span> files</span><span class=\"tree-summary-size\">(<span class=\"summary-number\">394.6 MB</span>)</span></div>"
    },
    "a Git pin, which has no sizes": {
      "classes": "tree-summary nav-metadata",
      "reads": "4 files",
      "pending": 0,
      "ignoredLine": "none",
      "numbers": [
        "4"
      ],
      "regular": "files",
      "html": "<div class=\"tree-summary nav-metadata\"><span class=\"tree-summary-count\"><span class=\"summary-number\">4</span> files</span><span class=\"tree-summary-size\"></span></div>"
    },
    "the split, nothing ignored": {
      "classes": "tree-summary tree-summary-split nav-metadata",
      "reads": "4 files (38 B)",
      "pending": 0,
      "ignoredLine": "none",
      "numbers": [
        "4",
        "38 B"
      ],
      "regular": "files ( )",
      "html": "<div class=\"tree-summary tree-summary-split nav-metadata\"><span class=\"tree-summary-tracked\"><span class=\"summary-number\">4</span> files</span><span class=\"tree-summary-bytes\">(<span class=\"summary-number\">38 B</span>)</span></div>"
    },
    "the split, with ignored files": {
      "classes": "tree-summary tree-summary-split nav-metadata",
      "reads": "12,797 files (394.6 MB) + 248,189 ignored (9.4 GB)",
      "pending": 0,
      "ignoredLine": "counted",
      "numbers": [
        "12,797",
        "394.6 MB",
        "248,189",
        "9.4 GB"
      ],
      "regular": "files ( ) + ignored ( )",
      "html": "<div class=\"tree-summary tree-summary-split nav-metadata\"><span class=\"tree-summary-tracked\"><span class=\"summary-number\">12,797</span> files</span><span class=\"tree-summary-bytes\">(<span class=\"summary-number\">394.6 MB</span>)</span><span class=\"tree-summary-ignored\"><span class=\"tree-summary-plus\">+</span><span><span class=\"summary-number\">248,189</span> ignored</span><span class=\"tree-summary-bytes\">(<span class=\"summary-number\">9.4 GB</span>)</span></span></div>"
    },
    "an empty folder": {
      "classes": "tree-summary tree-summary-split nav-metadata",
      "reads": "0 files (0 B)",
      "pending": 0,
      "ignoredLine": "none",
      "numbers": [
        "0",
        "0 B"
      ],
      "regular": "files ( )",
      "html": "<div class=\"tree-summary tree-summary-split nav-metadata\"><span class=\"tree-summary-tracked\"><span class=\"summary-number\">0</span> files</span><span class=\"tree-summary-bytes\">(<span class=\"summary-number\">0 B</span>)</span></div>"
    },
    "one file": {
      "classes": "tree-summary tree-summary-split nav-metadata",
      "reads": "1 file (2.0 KB)",
      "pending": 0,
      "ignoredLine": "none",
      "numbers": [
        "1",
        "2.0 KB"
      ],
      "regular": "file ( )",
      "html": "<div class=\"tree-summary tree-summary-split nav-metadata\"><span class=\"tree-summary-tracked\"><span class=\"summary-number\">1</span> file</span><span class=\"tree-summary-bytes\">(<span class=\"summary-number\">2.0 KB</span>)</span></div>"
    }
  },
  "totals": {
    "a root the walk has finished": {
      "files": 12797,
      "size": 413800000,
      "ignored_files": 248203,
      "ignored_size": 10100000000
    },
    "a root with nothing ignored": {
      "files": 51,
      "size": 369,
      "ignored_files": 0,
      "ignored_size": 0
    },
    "a root still being walked": null,
    "a Git revision's root, which keeps no ignored totals": null
  },
  "sequence": {
    "unknown: the ignored line held": {
      "classes": "tree-summary nav-metadata",
      "reads": "",
      "pending": 3,
      "ignoredLine": "held",
      "numbers": [],
      "regular": "",
      "html": "<div class=\"tree-summary nav-metadata\"><span class=\"tree-summary-count\"><span class=\"count tally-pending\"></span></span><span class=\"tree-summary-size\"><span class=\"size tally-pending\"></span></span><span class=\"tree-summary-ignored-pending mb-delayed-loading\" role=\"status\" aria-label=\"Counting ignored files\"><span class=\"tally-pending\" aria-hidden=\"true\"></span></span></div>"
    },
    "counted: the root's entry brings its ignored count": {
      "classes": "tree-summary tree-summary-split nav-metadata",
      "reads": "12,797 files (394.6 MB) + 248,203 ignored (9.4 GB)",
      "pending": 0,
      "ignoredLine": "counted",
      "numbers": [
        "12,797",
        "394.6 MB",
        "248,203",
        "9.4 GB"
      ],
      "regular": "files ( ) + ignored ( )",
      "html": "<div class=\"tree-summary tree-summary-split nav-metadata\"><span class=\"tree-summary-tracked\"><span class=\"summary-number\">12,797</span> files</span><span class=\"tree-summary-bytes\">(<span class=\"summary-number\">394.6 MB</span>)</span><span class=\"tree-summary-ignored\"><span class=\"tree-summary-plus\">+</span><span><span class=\"summary-number\">248,203</span> ignored</span><span class=\"tree-summary-bytes\">(<span class=\"summary-number\">9.4 GB</span>)</span></span></div>"
    },
    "none: the root's entry says nothing is ignored": {
      "classes": "tree-summary tree-summary-split nav-metadata",
      "reads": "51 files (369 B)",
      "pending": 0,
      "ignoredLine": "none",
      "numbers": [
        "51",
        "369 B"
      ],
      "regular": "files ( )",
      "html": "<div class=\"tree-summary tree-summary-split nav-metadata\"><span class=\"tree-summary-tracked\"><span class=\"summary-number\">51</span> files</span><span class=\"tree-summary-bytes\">(<span class=\"summary-number\">369 B</span>)</span></div>"
    }
  },
  "live": {
    "count still being counted": "<span class=\"count tally-pending\"></span>",
    "count known": "<span class=\"summary-number\">1</span> file",
    "count omitted": "",
    "size still being counted": "<span class=\"size tally-pending\"></span>",
    "size known": "(<span class=\"summary-number\">1.5 KB</span>)",
    "size omitted": ""
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
