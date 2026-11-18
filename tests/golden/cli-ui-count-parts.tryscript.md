---
cwd: ../..
sandbox: false
---
# Golden Test: A Count Summary’s Parts, Their One Painter, and the Brief Change Line

Every count summary comes in one shape of parts: words as strings, a number as
`{number}`, a list’s comma as `{punctuation}`, the dot between a line’s groups as
`{separator}`, and a status count, “21 A”, as `{status, letter, count}`. A separator on
a line whose name does not say it in words carries `spoken`, what a screen reader is
told in its place. `static/formatters.js` paints them, `countPartsNodes` as nodes and
`countPartsHtml` as markup, and the plugin SDK’s `mb.countPartsNodes` hands its parts to
the same function, so the Diff summary, a pull request’s Checks summary, a commit’s
hover card, and every shell count summary paint each kind in its one class.

A brief change line, “10 A, 5 D, 4 M · +1,234 −567”, is one component: `changeLine`
builds it from a change set’s statuses and line totals, and `changeLineNodes` and
`changeLineHtml` paint it, which the SDK exposes as `mb.changeLine` and
`mb.changeLineNodes`. The Diff summary’s header draws it after its “N files changed · ”,
and a commit’s hover card and totals line draw it too.
`changeSummary` says what a change set holds: its file count and its brief change line.

This browserless session runs the real formatter runtime and plugin SDK and records each
kind’s nodes, the brief change line’s nodes and markup, then each surface’s parts as the
markup they paint. The transcript pins these behaviors:

- A number is a `span.summary-number`, which the shell draws bold, and a comma a
  `span.summary-punctuation`, which it draws muted.
- A separator is a `span.summary-punctuation` hidden from assistive technology, and its
  `spoken`, when it has one, follows it in a `span.visually-hidden`.
- A status count is one `span.summary-status-count.file-change-status` that carries the
  status: its number in a `span.summary-number`, then a space and its letter, which the
  shell draws bold, number and letter alike, in the status’s ink.
- Words are text, escaped in markup.
- A brief change line is one `span.change-line`: its statuses in a
  `span.change-line-statuses`, which is one `span.change-line-group` with the dot after
  it, and its line totals, the inline change stats, in a `span.change-line-stats`. A
  line of no statuses is its totals alone, and a count it does not know is “?”. A screen
  reader is told the line in words, “10 added, 5 deleted, 4 modified; 1,234 lines added,
  567 deleted”.
- A change set’s summary reads “19 files changed · 10 A, 5 D, 4 M · +1,234 −567”, its
  file count then its brief change line, one file “1 file changed”, no files “0 files
  changed · +0 −0”, and totals that are not exact end in “(estimated)”. A commit’s hover
  card says its changes in the same words.
- A pull request’s Checks summary holds each dot to the count before it with a no-break
  space, and says a comma in its place.
- The session fails if the SDK builds or paints anything differently from the shell, if
  the markup says anything but the nodes, or if the painted text is not the text the
  parts and the line read as.

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
    "a status count": [
      {
        "tag": "span",
        "class": "summary-status-count file-change-status",
        "attributes": {
          "data-file-status": "added"
        },
        "children": [
          {
            "tag": "span",
            "class": "summary-number",
            "text": "21"
          },
          " A"
        ]
      }
    ],
    "words with markup in them": [
      "<b> & \"quotes\""
    ]
  },
  "changeLines": {
    "the owner's example": {
      "text": "10 A, 5 D, 4 M · +1,234 −567",
      "label": "10 added, 5 deleted, 4 modified; 1,234 lines added, 567 deleted",
      "nodes": [
        {
          "tag": "span",
          "class": "change-line",
          "children": [
            {
              "tag": "span",
              "class": "change-line-group",
              "children": [
                {
                  "tag": "span",
                  "class": "change-line-statuses",
                  "children": [
                    {
                      "tag": "span",
                      "class": "summary-status-count file-change-status",
                      "attributes": {
                        "data-file-status": "added"
                      },
                      "children": [
                        {
                          "tag": "span",
                          "class": "summary-number",
                          "text": "10"
                        },
                        " A"
                      ]
                    },
                    {
                      "tag": "span",
                      "class": "summary-punctuation",
                      "text": ","
                    },
                    " ",
                    {
                      "tag": "span",
                      "class": "summary-status-count file-change-status",
                      "attributes": {
                        "data-file-status": "removed"
                      },
                      "children": [
                        {
                          "tag": "span",
                          "class": "summary-number",
                          "text": "5"
                        },
                        " D"
                      ]
                    },
                    {
                      "tag": "span",
                      "class": "summary-punctuation",
                      "text": ","
                    },
                    " ",
                    {
                      "tag": "span",
                      "class": "summary-status-count file-change-status",
                      "attributes": {
                        "data-file-status": "modified"
                      },
                      "children": [
                        {
                          "tag": "span",
                          "class": "summary-number",
                          "text": "4"
                        },
                        " M"
                      ]
                    }
                  ]
                },
                {
                  "tag": "span",
                  "class": "summary-punctuation",
                  "attributes": {
                    "aria-hidden": "true"
                  },
                  "text": "·"
                }
              ]
            },
            {
              "tag": "span",
              "class": "change-line-stats",
              "children": [
                {
                  "tag": "span",
                  "class": "diff-stat-add",
                  "text": "+1,234"
                },
                {
                  "tag": "span",
                  "class": "diff-stat-del",
                  "text": "−567"
                }
              ]
            }
          ]
        }
      ]
    },
    "on a line with no name": {
      "text": "1 R · +5 −2",
      "label": "1 renamed; 5 lines added, 2 deleted",
      "html": "<span class=\"change-line\"><span class=\"change-line-group\"><span class=\"change-line-statuses\"><span class=\"summary-status-count file-change-status\" data-file-status=\"renamed\"><span class=\"summary-number\">1</span> R</span></span><span class=\"summary-punctuation\" aria-hidden=\"true\">·</span><span class=\"visually-hidden\">, </span></span><span class=\"change-line-stats\"><span class=\"diff-stat-add\">+5</span><span class=\"diff-stat-del\">−2</span></span></span>"
    },
    "no statuses": {
      "text": "+0 −0",
      "label": "0 lines added, 0 deleted",
      "html": "<span class=\"change-line\"><span class=\"change-line-stats\"><span class=\"diff-stat-add\">+0</span><span class=\"diff-stat-del\">−0</span></span></span>"
    },
    "line counts unknown": {
      "text": "? M · +? −?",
      "label": "? modified; line counts unknown",
      "html": "<span class=\"change-line\"><span class=\"change-line-group\"><span class=\"change-line-statuses\"><span class=\"summary-status-count file-change-status\" data-file-status=\"modified\"><span class=\"summary-number\">?</span> M</span></span><span class=\"summary-punctuation\" aria-hidden=\"true\">·</span></span><span class=\"change-line-stats\"><span class=\"diff-stat-add\">+?</span><span class=\"diff-stat-del\">−?</span></span></span>"
    }
  },
  "summaries": {
    "the Diff summary's header the reader asked for": {
      "text": "19 files changed · 10 A, 5 D, 4 M · +1,234 −567",
      "label": "19 files changed: 10 added, 5 deleted, 4 modified; 1,234 lines added, 567 deleted",
      "estimated": false,
      "files": "<span class=\"summary-number\">19</span> files changed",
      "line": "10 A, 5 D, 4 M · +1,234 −567"
    },
    "one renamed file": {
      "text": "1 file changed · 1 R · +5 −2",
      "label": "1 file changed: 1 renamed; 5 lines added, 2 deleted",
      "estimated": false,
      "files": "<span class=\"summary-number\">1</span> file changed",
      "line": "1 R · +5 −2"
    },
    "no files": {
      "text": "0 files changed · +0 −0",
      "label": "0 files changed; 0 lines added, 0 deleted",
      "estimated": false,
      "files": "<span class=\"summary-number\">0</span> files changed",
      "line": "+0 −0"
    },
    "totals that are not exact": {
      "text": "3 files changed · 3 M · +? −? (estimated)",
      "label": "3 files changed: 3 modified; line counts unknown, estimated",
      "estimated": true,
      "files": "<span class=\"summary-number\">3</span> files changed",
      "line": "3 M · +? −?"
    },
    "a commit's hover card": {
      "text": "32 files changed · 4 A, 28 M · +1,921 −160",
      "label": "32 files changed: 4 added, 28 modified; 1,921 lines added, 160 deleted",
      "estimated": false,
      "files": "<span class=\"summary-number\">32</span> files changed",
      "line": "4 A, 28 M · +1,921 −160"
    },
    "a commit's hover card whose counts are unknown": {
      "text": "? files changed · ? A, ? D, ? M · +? −?",
      "label": "? files changed: ? added, ? deleted, ? modified; line counts unknown",
      "estimated": false,
      "files": "<span class=\"summary-number\">?</span> files changed",
      "line": "? A, ? D, ? M · +? −?"
    }
  },
  "checks": "<span class=\"summary-number\">3</span> success <span class=\"summary-punctuation\" aria-hidden=\"true\">·</span><span class=\"visually-hidden\">, </span> <span class=\"summary-number\">1</span> failure"
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
