---
cwd: ../..
sandbox: false
---
# Golden Test: A Count Summary’s Parts and Their One Painter

Every count summary comes in one shape of parts: words as strings, a number as
`{number}`, a list’s comma as `{punctuation}`, the dot between a line’s groups as
`{separator}`, and a file change status as `{status, letter}`. A separator on a line
whose name does not say it in words carries `spoken`, what a screen reader is told in
its place. `static/formatters.js` paints them, `countPartsNodes` as nodes and
`countPartsHtml` as markup, and the plugin SDK’s `mb.countPartsNodes` hands its parts to
the same function, so the Diff summary, a pull request’s Checks summary, a commit’s
hover card, and every shell count summary paint each kind in its one class.
`changeSummary` beside them says what a change set holds, in the words the Diff
summary’s header and a commit’s hover card share.

This browserless session runs the real formatter runtime and plugin SDK and records each
kind’s nodes, then each surface’s parts as the markup they paint.
The transcript pins these behaviors:

- A number is a `span.summary-number`, which the shell draws bold, and a comma a
  `span.summary-punctuation`, which it draws muted.
- A separator is a `span.summary-punctuation` hidden from assistive technology, and its
  `spoken`, when it has one, follows it in a `span.visually-hidden`.
- A status is its letter in a `span.file-change-status` that carries the status, which
  the shell inks by it.
- Words are text, escaped in markup.
- A change set’s summary reads “19 files changed · 10 A, 5 D, 4 M · +1,234 −567”, one
  file “1 file changed”, no files “0 files changed · +0 −0”, and totals that are not
  exact end in “(estimated)”. A screen reader is told the statuses in words.
  A commit’s hover card says its changes in the same words, and a count it does not know
  is “?”.
- A pull request’s Checks summary holds each dot to the count before it with a no-break
  space, and says a comma in its place.
- The session fails if the SDK’s nodes differ from the shell’s, if the markup says
  anything but the nodes, or if the painted text is not the text the parts read as.

```console
$ node tests/dom/count-parts-session.js
{
  "kinds": {
    "words": [
      "files changed"
    ],
    "a number": [
      {
        "tag": "span",
        "class": "summary-number",
        "text": "12,797"
      }
    ],
    "a list's comma": [
      {
        "tag": "span",
        "class": "summary-punctuation",
        "text": ","
      }
    ],
    "a separator": [
      {
        "tag": "span",
        "class": "summary-punctuation",
        "attributes": {
          "aria-hidden": "true"
        },
        "text": "·"
      }
    ],
    "a separator that says a comma in its place": [
      {
        "tag": "span",
        "class": "summary-punctuation",
        "attributes": {
          "aria-hidden": "true"
        },
        "text": "·"
      },
      {
        "tag": "span",
        "class": "visually-hidden",
        "text": ", "
      }
    ],
    "a status": [
      {
        "tag": "span",
        "class": "file-change-status",
        "attributes": {
          "data-file-status": "added"
        },
        "text": "A"
      }
    ],
    "words with markup in them": [
      "<b> & \"quotes\""
    ]
  },
  "summaries": {
    "the Diff summary's header the reader asked for": {
      "text": "19 files changed · 10 A, 5 D, 4 M · +1,234 −567",
      "label": "19 files changed: 10 added, 5 deleted, 4 modified; 1,234 lines added, 567 deleted",
      "estimated": false,
      "files": "<span class=\"summary-number\">19</span> files changed",
      "breakdown": "<span class=\"summary-number\">10</span> <span class=\"file-change-status\" data-file-status=\"added\">A</span><span class=\"summary-punctuation\">,</span> <span class=\"summary-number\">5</span> <span class=\"file-change-status\" data-file-status=\"removed\">D</span><span class=\"summary-punctuation\">,</span> <span class=\"summary-number\">4</span> <span class=\"file-change-status\" data-file-status=\"modified\">M</span>",
      "totals": [
        "+1,234",
        "−567"
      ]
    },
    "one renamed file": {
      "text": "1 file changed · 1 R · +5 −2",
      "label": "1 file changed: 1 renamed; 5 lines added, 2 deleted",
      "estimated": false,
      "files": "<span class=\"summary-number\">1</span> file changed",
      "breakdown": "<span class=\"summary-number\">1</span> <span class=\"file-change-status\" data-file-status=\"renamed\">R</span>",
      "totals": [
        "+5",
        "−2"
      ]
    },
    "no files": {
      "text": "0 files changed · +0 −0",
      "label": "0 files changed; 0 lines added, 0 deleted",
      "estimated": false,
      "files": "<span class=\"summary-number\">0</span> files changed",
      "totals": [
        "+0",
        "−0"
      ]
    },
    "totals that are not exact": {
      "text": "3 files changed · 3 M · +? −? (estimated)",
      "label": "3 files changed: 3 modified; line counts unknown, estimated",
      "estimated": true,
      "files": "<span class=\"summary-number\">3</span> files changed",
      "breakdown": "<span class=\"summary-number\">3</span> <span class=\"file-change-status\" data-file-status=\"modified\">M</span>",
      "totals": [
        "+?",
        "−?"
      ]
    },
    "a commit's hover card": {
      "text": "32 files changed · 4 A, 28 M · +1,921 −160",
      "label": "32 files changed: 4 added, 28 modified; 1,921 lines added, 160 deleted",
      "estimated": false,
      "files": "<span class=\"summary-number\">32</span> files changed",
      "breakdown": "<span class=\"summary-number\">4</span> <span class=\"file-change-status\" data-file-status=\"added\">A</span><span class=\"summary-punctuation\">,</span> <span class=\"summary-number\">28</span> <span class=\"file-change-status\" data-file-status=\"modified\">M</span>",
      "totals": [
        "+1,921",
        "−160"
      ]
    },
    "a commit's hover card whose counts are unknown": {
      "text": "? files changed · ? A, ? D, ? M · +? −?",
      "label": "? files changed: ? added, ? deleted, ? modified; line counts unknown",
      "estimated": false,
      "files": "<span class=\"summary-number\">?</span> files changed",
      "breakdown": "<span class=\"summary-number\">?</span> <span class=\"file-change-status\" data-file-status=\"added\">A</span><span class=\"summary-punctuation\">,</span> <span class=\"summary-number\">?</span> <span class=\"file-change-status\" data-file-status=\"deleted\">D</span><span class=\"summary-punctuation\">,</span> <span class=\"summary-number\">?</span> <span class=\"file-change-status\" data-file-status=\"modified\">M</span>",
      "totals": [
        "+?",
        "−?"
      ]
    }
  },
  "checks": "<span class=\"summary-number\">3</span> success <span class=\"summary-punctuation\" aria-hidden=\"true\">·</span><span class=\"visually-hidden\">, </span> <span class=\"summary-number\">1</span> failure"
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
