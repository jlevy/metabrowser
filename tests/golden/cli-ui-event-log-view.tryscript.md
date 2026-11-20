---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: Metabrowser’s own event log, browsed in Metabrowser

A served `metab` writes a structured event log, and the event-log plugin draws an
`events-*.jsonl` file of it as four views: Timeline, Latency, By kind, and Errors.
The server counts, sorts, and nests, so each view is a route that `metab --api` reads
(`cli-api-event-log-views.tryscript.md`); this session pins what the page does with the
answers. It loads the plugin’s production modules, `event-log-model.js` and
`event-log-views.js`, and drives them through a scripted page whose answers are the
server’s, recorded in `tests/fixtures/event-log-view-*-responses.json` by
`tests/test_event_log_view_session.py`. The log is a server’s first four minutes while
`api.github.com`’s DNS answered with an address the network could not reach: a refresh
that could not connect, GitHub’s 503, and a comparison whose job and process had not
ended when the server was killed mid-line.

The Timeline reads a page of roots, 20 where the server’s own is 200, and each page
after it as long as the first and after the rows held.
A row with spans below opens to them, read when it opens and not again; any row opens to
its detail. A choice in the filter bar asks the server again with the filter, and closes
what was open. A view the page replaces or leaves draws nothing from an answer that
arrives late, and a file the server refuses is said so in an alert.

```console
$ node tests/dom/event-log-view-session.js
{
  "mounted, the answer not yet arrived": {
    "body": "event-log-body preview-empty mb-delayed-loading",
    "filters": 0
  },
  "the timeline's first page": {
    "requests": [
      "timeline?path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "summary": [
      "Records 58",
      "Spans 46",
      "Unfinished 2",
      "Covers 3 min 50 s",
      "From 2026-11-19 22:00:00 UTC"
    ],
    "notices": [
      "warning: 2 lines were not read: a torn last line, or a record of another schema version. Raw JSON shows every line."
    ],
    "filterGroups": [
      "event-log-kind",
      "event-log-outcome",
      "event-log-minimum"
    ],
    "kind chips": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcome chips": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never completed"
    ],
    "minimum choices": [
      "Any",
      "10 ms",
      "100 ms",
      "1.00 s",
      "2.00 s",
      "10.0 s"
    ],
    "rows": [
      "> lifecycle server.start +0.0 ms",
      "> request GET /view/ +899 ms 12 ms ok",
      "> request GET /api/tree +1000 ms 41 ms ok",
      "> request GET /api/plugin/github/pulls +4.90 s 2.41 s ok",
      "> request GET /api/file +7.90 s 3.1 ms ok",
      "> request GET /api/tree +8.90 s 8.4 ms ok"
    ],
    "rows shown": 20,
    "the last line": "[Show more (24 left)]"
  },
  "Show more reads the next page": {
    "requests": [
      "timeline?limit=20&offset=20&path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "rows shown": 40,
    "the last line": "[Show more (4 left)]"
  },
  "a request opens to the job it started": {
    "requests": [
      "timeline?parent=7007%3A22&path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "around": [
      "v request POST /api/plugin/github/pull-refresh +29.9 s 3.6 ms ok",
      "  > job mirror_refresh.MirrorSession._pull_job +29.9 s 32.0 s failed",
      "> request POST /api/plugin/github/pull-refresh +2 min 0 s 2.9 ms ok"
    ]
  },
  "and the job to the processes it ran": {
    "requests": [
      "timeline?parent=7007%3A23&path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "around": [
      "v request POST /api/plugin/github/pull-refresh +29.9 s 3.6 ms ok",
      "  v job mirror_refresh.MirrorSession._pull_job +29.9 s 32.0 s failed",
      "    > subprocess gh api +29.9 s 30.0 s failed",
      "    > probe probe api.github.com:443 +59.9 s 2.03 s failed",
      "> request POST /api/plugin/github/pull-refresh +2 min 0 s 2.9 ms ok"
    ]
  },
  "closing the request hides everything under it": {
    "requests": [],
    "around": [
      "> request POST /api/plugin/github/pull-refresh +29.9 s 3.6 ms ok",
      "> request POST /api/plugin/github/pull-refresh +2 min 0 s 2.9 ms ok"
    ]
  },
  "opening it again reads nothing again": {
    "requests": [],
    "around": [
      "v request POST /api/plugin/github/pull-refresh +29.9 s 3.6 ms ok",
      "  v job mirror_refresh.MirrorSession._pull_job +29.9 s 32.0 s failed",
      "    > subprocess gh api +29.9 s 30.0 s failed",
      "    > probe probe api.github.com:443 +59.9 s 2.03 s failed",
      "> request POST /api/plugin/github/pull-refresh +2 min 0 s 2.9 ms ok"
    ]
  },
  "a row with nothing below opens to its detail": {
    "requests": [],
    "expanded": "true",
    "detail": "event-log-detail",
    "facts": "Span7007:1Clientk3v9q2zx-1Began+899 msTook12 ms",
    "attributes": "{ \"status\": 200, \"bytes\": 4300, \"start_ms\": 11.5 }"
  },
  "and the next, which ends the log": {
    "requests": [
      "timeline?limit=20&offset=40&path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "rows shown": 47,
    "the last line": "> browser fetch GET /api/plugin/github/pull-comparison +3 min 20 s 30.0 s never completed"
  },
  "choosing the job kind asks again, with the filter": {
    "requests": [
      "timeline?kind=job&path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "rows": [
      "> request POST /api/plugin/github/pull-refresh +29.9 s 3.6 ms ok (context)",
      "> request POST /api/plugin/github/pull-refresh +2 min 0 s 2.9 ms ok (context)",
      "> request GET /api/plugin/github/pull-comparison +3 min 20 s 30.0 s cancelled (context)"
    ],
    "chips drawn with": "[\"job\"]"
  },
  "a filtered request opens to the jobs, with the filter": {
    "requests": [
      "timeline?kind=job&parent=7007%3A22&path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "rows": [
      "v request POST /api/plugin/github/pull-refresh +29.9 s 3.6 ms ok (context)",
      "  > job mirror_refresh.MirrorSession._pull_job +29.9 s 32.0 s failed",
      "> request POST /api/plugin/github/pull-refresh +2 min 0 s 2.9 ms ok (context)",
      "> request GET /api/plugin/github/pull-comparison +3 min 20 s 30.0 s cancelled (context)"
    ]
  },
  "adding an outcome narrows it, and an open row is closed": {
    "requests": [
      "timeline?kind=job&outcome=failed&path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "rows": [
      "> request POST /api/plugin/github/pull-refresh +29.9 s 3.6 ms ok (context)",
      "> request POST /api/plugin/github/pull-refresh +2 min 0 s 2.9 ms ok (context)"
    ]
  },
  "unchoosing the outcome keeps the kind": {
    "requests": [
      "timeline?kind=job&path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "rows": 3
  },
  "and unchoosing the kind asks for the whole log again": {
    "requests": [
      "timeline?path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "rows": 21
  },
  "what a choice in the bar asks of the server": {
    "chosen": {
      "kind": "job,request",
      "outcome": "timeout",
      "min_ms": "2000"
    },
    "after unchoosing job and the minimum": {
      "kind": "request",
      "outcome": "timeout"
    },
    "another key": null,
    "active": true
  },
  "Latency: the slowest, with their distribution": {
    "requests": [
      "slowest?path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "headings": [
      "Distribution of times",
      "Slowest · 49 of 49"
    ],
    "distribution": [
      "0  < 1.0 ms",
      "23  1.0 ms – 10 ms",
      "11  10 ms – 100 ms",
      "0  100 ms – 500 ms",
      "4  500 ms – 2.00 s",
      "4  2.00 s – 10.0 s",
      "7  ≥ 10.0 s"
    ],
    "rows": [
      "> browser wait githubPull:diffSummary +29.9 s 32.1 s ok",
      "> job mirror_refresh.MirrorSession._pull_job +29.9 s 32.0 s failed",
      "> subprocess gh api +29.9 s 30.0 s failed",
      "> request GET /api/plugin/github/pull-comparison +3 min 20 s 30.0 s cancelled",
      "> browser fetch GET /api/plugin/github/pull-comparison +3 min 20 s 30.0 s never completed",
      "> job comparison_cache.manifest +3 min 20 s 30.0 s unfinished",
      "> subprocess git diff-tree +3 min 20 s 30.0 s unfinished"
    ]
  },
  "a slow row opens to where it ran": {
    "requests": [],
    "path": "in GET /api/plugin/github/pull-comparison › comparison_cache.manifest",
    "facts": "Span7007:46Clientk3v9q2zx-90Began+3 min 20 sOpen records2"
  },
  "Latency, filtered to processes": {
    "requests": [
      "slowest?kind=subprocess&path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "rows": [
      "> subprocess gh api +29.9 s 30.0 s failed",
      "v subprocess git diff-tree +3 min 20 s 30.0 s unfinished",
      "> subprocess git fetch +2 min 5 s 1.81 s ok",
      "> subprocess gh api +2 min 1 s 689 ms failed",
      "> subprocess gh auth +2 min 0 s 623 ms ok"
    ]
  },
  "By kind: each kind and its names": {
    "requests": [
      "kinds?path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "sections": [
      {
        "heading": "request · 36",
        "outcomes": "ok 35 · cancelled 1 — median 4.4 ms, 95th 2.41 s, longest 30.0 s",
        "names": 7
      },
      {
        "heading": "job · 3",
        "outcomes": "failed 2 · unfinished 1 — median 30.0 s, 95th 32.0 s, longest 32.0 s",
        "names": 3
      },
      {
        "heading": "subprocess · 5",
        "outcomes": "failed 2 · ok 2 · unfinished 1 — median 1.81 s, 95th 30.0 s, longest 30.0 s",
        "names": 4
      },
      {
        "heading": "browser · 5",
        "outcomes": "none 2 · ok 2 · never completed 1 — median 30.0 s, 95th 32.1 s, longest 32.1 s",
        "names": 4
      },
      {
        "heading": "lifecycle · 1",
        "outcomes": "none 1",
        "names": 1
      },
      {
        "heading": "loop · 1",
        "outcomes": "ok 1 — median 2.41 s, 95th 2.41 s, longest 2.41 s",
        "names": 1
      },
      {
        "heading": "probe · 1",
        "outcomes": "failed 1 — median 2.03 s, 95th 2.03 s, longest 2.03 s",
        "names": 1
      }
    ],
    "the first table": [
      "GET /api/plugin/github/pull-comparison",
      "1",
      "0",
      "30.0 s",
      "30.0 s",
      "30.0 s",
      "30.0 s"
    ]
  },
  "By kind, of what failed": {
    "requests": [
      "kinds?outcome=failed&path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "sections": [
      "job · 2",
      "subprocess · 2",
      "probe · 1"
    ]
  },
  "Errors: the causes first, the page's reports apart": {
    "requests": [
      "errors?path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "parts of the view": [
      "event-log-head",
      "event-log-body"
    ],
    "headings": [
      "Failures by cause · 5",
      "Last failed connectivity probe",
      "Still running when the log ended · 2",
      "What the pages reported · 1"
    ],
    "causes": [
      [
        "connect timeout · 3",
        "GitHub could not be reached because the connection to api.github.com at 20.172.24.160 timed out after 2 s; other sites are reachable",
        "Addresses that failed: 20.172.24.160",
        "mirror_refresh.MirrorSession._pull_job 1 · gh api 1 · probe api.github.com:443 1",
        "First 22:01:00.016 · last 22:01:02.051 UTC",
        [
          "probe probe api.github.com:443 — failed after 2.03 s (in POST /api/plugin/github/pull-refresh › mirror_refresh.MirrorSession._pull_job)",
          "job mirror_refresh.MirrorSession._pull_job — failed after 32.0 s (in POST /api/plugin/github/pull-refresh)",
          "subprocess gh api — failed after 30.0 s (in POST /api/plugin/github/pull-refresh › mirror_refresh.MirrorSession._pull_job)"
        ]
      ],
      [
        "server error · 2",
        "GitHub answered HTTP 503",
        "pull_files_refresh.refresh_files 1 · gh api 1",
        "First 22:02:01.328 · last 22:02:01.331 UTC",
        [
          "job pull_files_refresh.refresh_files — failed after 1.33 s (in POST /api/plugin/github/pull-refresh)",
          "subprocess gh api — failed after 689 ms (in POST /api/plugin/github/pull-refresh › pull_files_refresh.refresh_files)"
        ]
      ]
    ],
    "unfinished": [
      "> job comparison_cache.manifest +3 min 20 s 30.0 s unfinished",
      "> subprocess git diff-tree +3 min 20 s 30.0 s unfinished"
    ]
  },
  "a file the server refuses is said so, in an alert": {
    "requests": [
      "errors?path=absent.jsonl"
    ],
    "body": [
      "notice error: Could not read the event log: Not found"
    ]
  },
  "a view replaced or disposed while its answer was out draws nothing": {
    "requests": [
      "kinds?path=events-20261119T220000Z-p7007-000.jsonl",
      "slowest?path=events-20261119T220000Z-p7007-000.jsonl"
    ],
    "body": "event-log-body preview-empty mb-delayed-loading",
    "rows": []
  },
  "a duration reads in the unit a person reads": {
    "999": "999 ms",
    "32100": "32.1 s",
    "125000": "2 min 5 s",
    "4000000": "1 h 6 min",
    "0.04": "0.0 ms",
    "3.6": "3.6 ms",
    "41.2": "41 ms",
    "2412.5": "2.41 s",
    "15007.8": "15.0 s"
  },
  "the distribution's buckets are named from the server's edges": [
    "< 1.0 ms",
    "1.0 ms – 10 ms",
    "10 ms – 100 ms",
    "100 ms – 500 ms",
    "500 ms – 2.00 s",
    "2.00 s – 10.0 s",
    "≥ 10.0 s"
  ],
  "a bar sits on the log's time axis and is never invisible": {
    "start of the log": {
      "left": 0,
      "width": 0.1
    },
    "a hairline": {
      "left": 0.0022,
      "width": 0.003
    },
    "past the end": {
      "left": 0.9,
      "width": 0.1
    },
    "no extent": {
      "left": 0,
      "width": 1
    },
    "a share of the longest": 0.25
  },
  "requests asked of the server": {
    "unrecorded": []
  }
}
? 0
```
