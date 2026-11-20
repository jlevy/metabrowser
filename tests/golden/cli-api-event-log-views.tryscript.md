---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  METABROWSER_EVENT_LOG: "0"
before: >-
  mkdir root &&
  cp "$TRYSCRIPT_TEST_DIR/../fixtures/event-log-views/events-20261119T220000Z-p7007-000.jsonl" root/ &&
  printf '{"type":"system","subtype":"init","session_id":"s1","model":"m1"}\n' > root/session.jsonl &&
  printf '{"unrelated":true}\n{"also":"not an event"}\n' > root/events.jsonl &&
  printf '{"v":1,"ts":"2026-11-19T23:00:00.000Z","event":"mark","kind":"lifecycle","name":"server.start","pid":9}\n' > root/events-20261119T230000Z-p9-000.jsonl &&
  touch -t 202611192300.00 root/events-20261119T230000Z-p9-000.jsonl
---
# Golden tests: the event log, browsed as spans, through `--api`

Metabrowser’s own event log is a JSON Lines file per served process, `events-*.jsonl`
(`metabrowser.event_log`), and the event-log plugin reads one as spans: each unit of
work with the work it started under it, how long it took, and how it ended.
`/api/plugin/event-log/` has a route for each view of it: `timeline`, `slowest`,
`kinds`, and `errors`. Each reads the file named by `path` through the content reader
and takes the filters `/api/event-log` takes.
The kind is picked for a file of an attached folder only (its name match is a filesystem
one), so these views open there.

The fixture segment is a server’s first four minutes serving a GitHub repository while
`api.github.com`’s DNS answered with an address the network could not reach, as on the
owner’s machine on 2026-11-19: a refresh whose `gh` call timed out connecting and whose
probe found the same, GitHub’s 503 on the next, a comparison whose job and `git` process
had not ended when the server was killed mid-line, and a page that reported two waits.
The torn last line, and a line of a later schema version, are counted and skipped.

## Test: a `.jsonl` file named for the log is an event log

`events.jsonl` is a JSONL file with another name, and stays a generic log.

```console
$ metab root --show events-20261119T220000Z-p7007-000.jsonl
show: events-20261119T220000Z-p7007-000.jsonl
route: /view/events-20261119T220000Z-p7007-000.jsonl
kind: event-log
views: timeline (default, key V), latency (key L), kinds (key B), errors (key E), raw (key S)
model: jsonl envelope; size=14917
? 0
```

```console
$ metab root --show events.jsonl
show: events.jsonl
route: /view/events.jsonl
kind: unknown-jsonl
views: log (default, key V), raw (key S)
model: jsonl envelope; size=43
? 0
```

```console
$ metab root --show session.jsonl
show: session.jsonl
route: /view/session.jsonl
kind: agent-log
views: session (default, key E), log (key V), charts (key C), raw (key S)
model: jsonl envelope; size=66
? 0
```

## Test: the file envelope names the kind and its views

A segment the server has just opened holds one record; its envelope says it is an event
log and lists the views it opens with, the default first.

```console
$ metab root --api '/api/file?path=events-20261119T230000Z-p9-000.jsonl'
api: /api/file?path=events-20261119T230000Z-p9-000.jsonl
status: 200
{
  "type": "jsonl",
  "kind": "event-log",
  "views": [
    {
      "id": "timeline",
      "label": "Timeline",
      "key": "v",
      "default": true,
      "container_class": "content-body",
      "printable": false,
      "print_profile": "plain",
      "render_runtime": null
    },
    {
      "id": "latency",
      "label": "Latency",
      "key": "l",
      "default": false,
      "container_class": "content-body",
      "printable": false,
      "print_profile": "plain",
      "render_runtime": null
    },
    {
      "id": "kinds",
      "label": "By kind",
      "key": "b",
      "default": false,
      "container_class": "content-body",
      "printable": false,
      "print_profile": "plain",
      "render_runtime": null
    },
    {
      "id": "errors",
      "label": "Errors",
      "key": "e",
      "default": false,
      "container_class": "content-body",
      "printable": false,
      "print_profile": "plain",
      "render_runtime": null
    },
    {
      "id": "raw",
      "label": "Raw JSON",
      "key": "s",
      "default": false,
      "container_class": "content-body",
      "printable": false,
      "print_profile": "plain",
      "render_runtime": null
    }
  ],
  "path": "events-20261119T230000Z-p9-000.jsonl",
  "size": 104,
  "mtime": 1795129200.0,
  "mtime_hash": "events_20261119T230000Z_p9_000_js_nq8bwm32t47e6kmgk5sq3eg8w7j6zr9",
  "summary": {
    "adapter": "unknown",
    "total_events": 1,
    "tool_calls": 0,
    "errors": 0,
    "cost_usd": null,
    "duration_s": null,
    "is_done": false,
    "is_error": false
  },
  "events": [
    {
      "kind": "unknown",
      "summary": "[unknown] {'v': 1, 'ts': '2026-11-19T23:00:00.000Z', 'event': 'mark', 'kind': 'lifecycle', 'name': 'server.start', 'pid': 9}",
      "adapter": "unknown",
      "provider": null,
      "timestamp": null,
      "is_error": false,
      "is_done": false,
      "cost_usd": null,
      "duration_s": null,
      "raw": {
        "v": 1,
        "ts": "2026-11-19T23:00:00.000Z",
        "event": "mark",
        "kind": "lifecycle",
        "name": "server.start",
        "pid": 9
      },
      "summary_parts": null
    }
  ],
  "raw_text": "{\n  \"v\": 1,\n  \"ts\": \"2026-11-19T23:00:00.000Z\",\n  \"event\": \"mark\",\n  \"kind\": \"lifecycle\",\n  \"name\": \"server.start\",\n  \"pid\": 9\n}",
  "raw_truncation": null,
  "bytes_read": 104
}
? 0
```

## Test: the timeline’s roots, in time order

`limit` and `offset` take a page; `total` and `has_more` say what follows.
A mark, a span, and what a page reported sit among the roots, and a span says how many
spans are directly below it and how many in all.

```console
$ metab root --api '/api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&offset=22&limit=2'
api: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&offset=22&limit=2
status: 200
{
  "view": "timeline",
  "log": {
    "schema_version": 1,
    "kinds": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcomes": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never_completed"
    ],
    "edges_ms": [
      1.0,
      10.0,
      100.0,
      500.0,
      2000.0,
      10000.0
    ],
    "bytes": 14917,
    "records": 58,
    "skipped": 2,
    "spans": 46,
    "unfinished": 2,
    "started": "2026-11-19T22:00:00.100Z",
    "ended": "2026-11-19T22:03:50.003Z",
    "extent_ms": 229903.0,
    "pids": [
      7007
    ],
    "continues": false
  },
  "query": {
    "kind": [],
    "outcome": [],
    "name": null,
    "client": null,
    "cause": null,
    "min_ms": null
  },
  "order": "oldest",
  "parent": null,
  "total": 44,
  "offset": 22,
  "limit": 2,
  "max_limit": 1000,
  "has_more": true,
  "rows": [
    {
      "type": "span",
      "key": "7007:22",
      "kind": "request",
      "name": "POST /api/plugin/github/pull-refresh",
      "start_ms": 29899.4,
      "dur_ms": 3.6,
      "outcome": "ok",
      "state": "ended",
      "client": "k3v9q2zx-41",
      "pid": 7007,
      "span": 22,
      "parent": null,
      "attrs": {
        "status": 202,
        "bytes": 693,
        "query": "number=615",
        "start_ms": 3.4
      },
      "elapsed_ms": 3.6,
      "children": 1,
      "below": 3,
      "matched": true
    },
    {
      "type": "report",
      "key": "7007@29",
      "kind": "browser",
      "name": "wait githubPull:diffSummary",
      "start_ms": 29900.0,
      "dur_ms": 10000.0,
      "outcome": null,
      "state": "report",
      "client": "k3v9q2zx",
      "pid": 7007,
      "span": null,
      "parent": null,
      "attrs": {
        "threshold_ms": 10000.0,
        "detail": {
          "number": 615
        },
        "path": "/pull/615"
      },
      "elapsed_ms": null,
      "event": "open",
      "children": 0,
      "below": 0,
      "matched": true
    }
  ]
}
? 0
```

## Test: the spans a job started, and the processes it ran

```console
$ metab root --api '/api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&parent=7007:23'
api: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&parent=7007:23
status: 200
{
  "view": "timeline",
  "log": {
    "schema_version": 1,
    "kinds": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcomes": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never_completed"
    ],
    "edges_ms": [
      1.0,
      10.0,
      100.0,
      500.0,
      2000.0,
      10000.0
    ],
    "bytes": 14917,
    "records": 58,
    "skipped": 2,
    "spans": 46,
    "unfinished": 2,
    "started": "2026-11-19T22:00:00.100Z",
    "ended": "2026-11-19T22:03:50.003Z",
    "extent_ms": 229903.0,
    "pids": [
      7007
    ],
    "continues": false
  },
  "query": {
    "kind": [],
    "outcome": [],
    "name": null,
    "client": null,
    "cause": null,
    "min_ms": null
  },
  "order": "oldest",
  "parent": "7007:23",
  "total": 2,
  "offset": 0,
  "limit": 200,
  "max_limit": 1000,
  "has_more": false,
  "rows": [
    {
      "type": "span",
      "key": "7007:24",
      "kind": "subprocess",
      "name": "gh api",
      "start_ms": 29909.6,
      "dur_ms": 30006.4,
      "outcome": "failed",
      "state": "ended",
      "client": "k3v9q2zx-41",
      "pid": 7007,
      "span": 24,
      "parent": "7007:23",
      "attrs": {
        "args": [
          "api",
          "graphql",
          "-f",
          "query=…"
        ],
        "timeout_s": 30.0,
        "exit": 1,
        "stdout_bytes": 0,
        "cause": "connect_timeout",
        "address": "20.172.24.160",
        "failure": "exit",
        "failure_message": "Post \"https://api.github.com/graphql\": dial tcp 20.172.24.160:443: i/o timeout"
      },
      "elapsed_ms": 30006.4,
      "children": 0,
      "below": 0,
      "matched": true
    },
    {
      "type": "span",
      "key": "7007:25",
      "kind": "probe",
      "name": "probe api.github.com:443",
      "start_ms": 59919.8,
      "dur_ms": 2031.2,
      "outcome": "failed",
      "state": "ended",
      "client": "k3v9q2zx-41",
      "pid": 7007,
      "span": 25,
      "parent": "7007:23",
      "attrs": {
        "timeout_s": 3.0,
        "via_proxy": false,
        "target": "api.github.com:443",
        "verdict": "connect_timeout",
        "dns_ms": 6.6,
        "addresses": [
          {
            "address": "20.172.24.160",
            "result": "timeout",
            "ms": 1993.0
          }
        ],
        "control": {
          "target": "captive.apple.com:80",
          "verdict": "reachable"
        },
        "cause": "connect_timeout",
        "message": "GitHub could not be reached because the connection to api.github.com at 20.172.24.160 timed out after 2 s; other sites are reachable"
      },
      "elapsed_ms": 2031.2,
      "children": 0,
      "below": 0,
      "matched": true
    }
  ]
}
? 0
```

## Test: a filter keeps the spans that match and those above them

Only the jobs: the requests that started them are shown as context (`matched` is false),
with only the children that lead to a match.

```console
$ metab root --api '/api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&kind=job&outcome=failed,never_completed'
api: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&kind=job&outcome=failed,never_completed
status: 200
{
  "view": "timeline",
  "log": {
    "schema_version": 1,
    "kinds": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcomes": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never_completed"
    ],
    "edges_ms": [
      1.0,
      10.0,
      100.0,
      500.0,
      2000.0,
      10000.0
    ],
    "bytes": 14917,
    "records": 58,
    "skipped": 2,
    "spans": 46,
    "unfinished": 2,
    "started": "2026-11-19T22:00:00.100Z",
    "ended": "2026-11-19T22:03:50.003Z",
    "extent_ms": 229903.0,
    "pids": [
      7007
    ],
    "continues": false
  },
  "query": {
    "kind": [
      "job"
    ],
    "outcome": [
      "failed",
      "never_completed"
    ],
    "name": null,
    "client": null,
    "cause": null,
    "min_ms": null
  },
  "order": "oldest",
  "parent": null,
  "total": 2,
  "offset": 0,
  "limit": 200,
  "max_limit": 1000,
  "has_more": false,
  "rows": [
    {
      "type": "span",
      "key": "7007:22",
      "kind": "request",
      "name": "POST /api/plugin/github/pull-refresh",
      "start_ms": 29899.4,
      "dur_ms": 3.6,
      "outcome": "ok",
      "state": "ended",
      "client": "k3v9q2zx-41",
      "pid": 7007,
      "span": 22,
      "parent": null,
      "attrs": {
        "status": 202,
        "bytes": 693,
        "query": "number=615",
        "start_ms": 3.4
      },
      "elapsed_ms": 3.6,
      "children": 1,
      "below": 1,
      "matched": false
    },
    {
      "type": "span",
      "key": "7007:38",
      "kind": "request",
      "name": "POST /api/plugin/github/pull-refresh",
      "start_ms": 119899.1,
      "dur_ms": 2.9,
      "outcome": "ok",
      "state": "ended",
      "client": "k3v9q2zx-70",
      "pid": 7007,
      "span": 38,
      "parent": null,
      "attrs": {
        "status": 202,
        "bytes": 693,
        "query": "number=615",
        "start_ms": 2.7
      },
      "elapsed_ms": 2.9,
      "children": 1,
      "below": 1,
      "matched": false
    }
  ]
}
? 0
```

## Test: the slowest, longest first, with the distribution of every time

A span that never ended counts for the time it had run when the log did.

```console
$ metab root --api '/api/plugin/event-log/slowest?path=events-20261119T220000Z-p7007-000.jsonl&limit=3'
api: /api/plugin/event-log/slowest?path=events-20261119T220000Z-p7007-000.jsonl&limit=3
status: 200
{
  "view": "slowest",
  "log": {
    "schema_version": 1,
    "kinds": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcomes": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never_completed"
    ],
    "edges_ms": [
      1.0,
      10.0,
      100.0,
      500.0,
      2000.0,
      10000.0
    ],
    "bytes": 14917,
    "records": 58,
    "skipped": 2,
    "spans": 46,
    "unfinished": 2,
    "started": "2026-11-19T22:00:00.100Z",
    "ended": "2026-11-19T22:03:50.003Z",
    "extent_ms": 229903.0,
    "pids": [
      7007
    ],
    "continues": false
  },
  "query": {
    "kind": [],
    "outcome": [],
    "name": null,
    "client": null,
    "cause": null,
    "min_ms": null
  },
  "edges_ms": [
    1.0,
    10.0,
    100.0,
    500.0,
    2000.0,
    10000.0
  ],
  "histogram": [
    0,
    23,
    11,
    0,
    4,
    4,
    7
  ],
  "timed": 49,
  "limit": 3,
  "max_limit": 1000,
  "items": [
    {
      "type": "report",
      "key": "7007@41",
      "kind": "browser",
      "name": "wait githubPull:diffSummary",
      "start_ms": 29900.0,
      "dur_ms": 32100.0,
      "outcome": "ok",
      "state": "report",
      "client": "k3v9q2zx",
      "pid": 7007,
      "span": null,
      "parent": null,
      "attrs": {
        "threshold_ms": 10000.0,
        "detail": {
          "number": 615
        },
        "path": "/pull/615"
      },
      "elapsed_ms": 32100.0,
      "event": "end",
      "path": []
    },
    {
      "type": "span",
      "key": "7007:23",
      "kind": "job",
      "name": "mirror_refresh.MirrorSession._pull_job",
      "start_ms": 29901.0,
      "dur_ms": 32050.0,
      "outcome": "failed",
      "state": "ended",
      "client": "k3v9q2zx-41",
      "pid": 7007,
      "span": 23,
      "parent": "7007:22",
      "attrs": {
        "key": "demo:pull/615",
        "network": true,
        "queued_ms": 0.2,
        "cause": "connect_timeout",
        "failure": "network_error",
        "failure_message": "GitHub could not be reached because the connection to api.github.com at 20.172.24.160 timed out after 2 s; other sites are reachable"
      },
      "elapsed_ms": 32050.0,
      "path": [
        {
          "key": "7007:22",
          "kind": "request",
          "name": "POST /api/plugin/github/pull-refresh"
        }
      ]
    },
    {
      "type": "span",
      "key": "7007:24",
      "kind": "subprocess",
      "name": "gh api",
      "start_ms": 29909.6,
      "dur_ms": 30006.4,
      "outcome": "failed",
      "state": "ended",
      "client": "k3v9q2zx-41",
      "pid": 7007,
      "span": 24,
      "parent": "7007:23",
      "attrs": {
        "args": [
          "api",
          "graphql",
          "-f",
          "query=…"
        ],
        "timeout_s": 30.0,
        "exit": 1,
        "stdout_bytes": 0,
        "cause": "connect_timeout",
        "address": "20.172.24.160",
        "failure": "exit",
        "failure_message": "Post \"https://api.github.com/graphql\": dial tcp 20.172.24.160:443: i/o timeout"
      },
      "elapsed_ms": 30006.4,
      "path": [
        {
          "key": "7007:22",
          "kind": "request",
          "name": "POST /api/plugin/github/pull-refresh"
        },
        {
          "key": "7007:23",
          "kind": "job",
          "name": "mirror_refresh.MirrorSession._pull_job"
        }
      ]
    }
  ]
}
? 0
```

```console
$ metab root --api '/api/plugin/event-log/slowest?path=events-20261119T220000Z-p7007-000.jsonl&kind=subprocess&min_ms=1000&limit=2'
api: /api/plugin/event-log/slowest?path=events-20261119T220000Z-p7007-000.jsonl&kind=subprocess&min_ms=1000&limit=2
status: 200
{
  "view": "slowest",
  "log": {
    "schema_version": 1,
    "kinds": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcomes": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never_completed"
    ],
    "edges_ms": [
      1.0,
      10.0,
      100.0,
      500.0,
      2000.0,
      10000.0
    ],
    "bytes": 14917,
    "records": 58,
    "skipped": 2,
    "spans": 46,
    "unfinished": 2,
    "started": "2026-11-19T22:00:00.100Z",
    "ended": "2026-11-19T22:03:50.003Z",
    "extent_ms": 229903.0,
    "pids": [
      7007
    ],
    "continues": false
  },
  "query": {
    "kind": [
      "subprocess"
    ],
    "outcome": [],
    "name": null,
    "client": null,
    "cause": null,
    "min_ms": 1000.0
  },
  "edges_ms": [
    1.0,
    10.0,
    100.0,
    500.0,
    2000.0,
    10000.0
  ],
  "histogram": [
    0,
    0,
    0,
    0,
    1,
    0,
    2
  ],
  "timed": 3,
  "limit": 2,
  "max_limit": 1000,
  "items": [
    {
      "type": "span",
      "key": "7007:24",
      "kind": "subprocess",
      "name": "gh api",
      "start_ms": 29909.6,
      "dur_ms": 30006.4,
      "outcome": "failed",
      "state": "ended",
      "client": "k3v9q2zx-41",
      "pid": 7007,
      "span": 24,
      "parent": "7007:23",
      "attrs": {
        "args": [
          "api",
          "graphql",
          "-f",
          "query=…"
        ],
        "timeout_s": 30.0,
        "exit": 1,
        "stdout_bytes": 0,
        "cause": "connect_timeout",
        "address": "20.172.24.160",
        "failure": "exit",
        "failure_message": "Post \"https://api.github.com/graphql\": dial tcp 20.172.24.160:443: i/o timeout"
      },
      "elapsed_ms": 30006.4,
      "path": [
        {
          "key": "7007:22",
          "kind": "request",
          "name": "POST /api/plugin/github/pull-refresh"
        },
        {
          "key": "7007:23",
          "kind": "job",
          "name": "mirror_refresh.MirrorSession._pull_job"
        }
      ]
    },
    {
      "type": "span",
      "key": "7007:46",
      "kind": "subprocess",
      "name": "git diff-tree",
      "start_ms": 199930.0,
      "dur_ms": null,
      "outcome": null,
      "state": "unfinished",
      "client": "k3v9q2zx-90",
      "pid": 7007,
      "span": 46,
      "parent": "7007:45",
      "attrs": {
        "args": [
          "diff-tree",
          "--raw",
          "-z",
          "4922384",
          "519dabc"
        ],
        "timeout_s": 900.0
      },
      "elapsed_ms": 29973.0,
      "opens": 2,
      "path": [
        {
          "key": "7007:44",
          "kind": "request",
          "name": "GET /api/plugin/github/pull-comparison"
        },
        {
          "key": "7007:45",
          "kind": "job",
          "name": "comparison_cache.manifest"
        }
      ]
    }
  ]
}
? 0
```

## Test: each kind and name, counted, timed, and ended

```console
$ metab root --api '/api/plugin/event-log/kinds?path=events-20261119T220000Z-p7007-000.jsonl&kind=job,subprocess'
api: /api/plugin/event-log/kinds?path=events-20261119T220000Z-p7007-000.jsonl&kind=job,subprocess
status: 200
{
  "view": "kinds",
  "log": {
    "schema_version": 1,
    "kinds": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcomes": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never_completed"
    ],
    "edges_ms": [
      1.0,
      10.0,
      100.0,
      500.0,
      2000.0,
      10000.0
    ],
    "bytes": 14917,
    "records": 58,
    "skipped": 2,
    "spans": 46,
    "unfinished": 2,
    "started": "2026-11-19T22:00:00.100Z",
    "ended": "2026-11-19T22:03:50.003Z",
    "extent_ms": 229903.0,
    "pids": [
      7007
    ],
    "continues": false
  },
  "query": {
    "kind": [
      "job",
      "subprocess"
    ],
    "outcome": [],
    "name": null,
    "client": null,
    "cause": null,
    "min_ms": null
  },
  "edges_ms": [
    1.0,
    10.0,
    100.0,
    500.0,
    2000.0,
    10000.0
  ],
  "histogram": [
    0,
    0,
    0,
    0,
    4,
    0,
    4
  ],
  "kinds": [
    {
      "kind": "job",
      "count": 3,
      "timed": 3,
      "outcomes": {
        "failed": 2,
        "unfinished": 1
      },
      "p50_ms": 29993.0,
      "p95_ms": 32050.0,
      "max_ms": 32050.0,
      "total_ms": 63373.6,
      "histogram": [
        0,
        0,
        0,
        0,
        1,
        0,
        2
      ],
      "names": [
        {
          "name": "mirror_refresh.MirrorSession._pull_job",
          "count": 1,
          "failed": 1,
          "p50_ms": 32050.0,
          "p95_ms": 32050.0,
          "max_ms": 32050.0,
          "total_ms": 32050.0
        },
        {
          "name": "comparison_cache.manifest",
          "count": 1,
          "failed": 1,
          "p50_ms": 29993.0,
          "p95_ms": 29993.0,
          "max_ms": 29993.0,
          "total_ms": 29993.0
        },
        {
          "name": "pull_files_refresh.refresh_files",
          "count": 1,
          "failed": 1,
          "p50_ms": 1330.6,
          "p95_ms": 1330.6,
          "max_ms": 1330.6,
          "total_ms": 1330.6
        }
      ],
      "names_more": 0
    },
    {
      "kind": "subprocess",
      "count": 5,
      "timed": 5,
      "outcomes": {
        "failed": 2,
        "ok": 2,
        "unfinished": 1
      },
      "p50_ms": 1810.2,
      "p95_ms": 30006.4,
      "max_ms": 30006.4,
      "total_ms": 63101.9,
      "histogram": [
        0,
        0,
        0,
        0,
        3,
        0,
        2
      ],
      "names": [
        {
          "name": "gh api",
          "count": 2,
          "failed": 2,
          "p50_ms": 688.9,
          "p95_ms": 30006.4,
          "max_ms": 30006.4,
          "total_ms": 30695.3
        },
        {
          "name": "git diff-tree",
          "count": 1,
          "failed": 1,
          "p50_ms": 29973.0,
          "p95_ms": 29973.0,
          "max_ms": 29973.0,
          "total_ms": 29973.0
        },
        {
          "name": "git fetch",
          "count": 1,
          "failed": 0,
          "p50_ms": 1810.2,
          "p95_ms": 1810.2,
          "max_ms": 1810.2,
          "total_ms": 1810.2
        },
        {
          "name": "gh auth",
          "count": 1,
          "failed": 0,
          "p50_ms": 623.4,
          "p95_ms": 623.4,
          "max_ms": 623.4,
          "total_ms": 623.4
        }
      ],
      "names_more": 0
    }
  ]
}
? 0
```

## Test: failures by cause, the page’s reports apart, and what never ended

The grouping is `/api/event-log/failures`’s, over the whole file: the cause first, then
the messages and addresses.
What a page saw is listed apart, because it says what the page saw and not why.

```console
$ metab root --api '/api/plugin/event-log/errors?path=events-20261119T220000Z-p7007-000.jsonl'
api: /api/plugin/event-log/errors?path=events-20261119T220000Z-p7007-000.jsonl
status: 200
{
  "view": "errors",
  "log": {
    "schema_version": 1,
    "kinds": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcomes": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never_completed"
    ],
    "edges_ms": [
      1.0,
      10.0,
      100.0,
      500.0,
      2000.0,
      10000.0
    ],
    "bytes": 14917,
    "records": 58,
    "skipped": 2,
    "spans": 46,
    "unfinished": 2,
    "started": "2026-11-19T22:00:00.100Z",
    "ended": "2026-11-19T22:03:50.003Z",
    "extent_ms": 229903.0,
    "pids": [
      7007
    ],
    "continues": false
  },
  "kinds": [],
  "failures": 5,
  "causes": [
    {
      "cause": "connect_timeout",
      "source": "cause",
      "count": 3,
      "kinds": {
        "job": 1,
        "subprocess": 1,
        "probe": 1
      },
      "names": {
        "mirror_refresh.MirrorSession._pull_job": 1,
        "gh api": 1,
        "probe api.github.com:443": 1
      },
      "first": "2026-11-19T22:01:00.016Z",
      "last": "2026-11-19T22:01:02.051Z",
      "message": "GitHub could not be reached because the connection to api.github.com at 20.172.24.160 timed out after 2 s; other sites are reachable",
      "addresses": [
        "20.172.24.160"
      ],
      "examples": [
        {
          "ts": "2026-11-19T22:01:02.051Z",
          "key": "7007:25",
          "pid": 7007,
          "span": 25,
          "kind": "probe",
          "name": "probe api.github.com:443",
          "outcome": "failed",
          "dur_ms": 2031.2,
          "address": null,
          "path": [
            {
              "key": "7007:22",
              "kind": "request",
              "name": "POST /api/plugin/github/pull-refresh"
            },
            {
              "key": "7007:23",
              "kind": "job",
              "name": "mirror_refresh.MirrorSession._pull_job"
            }
          ]
        },
        {
          "ts": "2026-11-19T22:01:02.051Z",
          "key": "7007:23",
          "pid": 7007,
          "span": 23,
          "kind": "job",
          "name": "mirror_refresh.MirrorSession._pull_job",
          "outcome": "failed",
          "dur_ms": 32050.0,
          "address": null,
          "path": [
            {
              "key": "7007:22",
              "kind": "request",
              "name": "POST /api/plugin/github/pull-refresh"
            }
          ]
        },
        {
          "ts": "2026-11-19T22:01:00.016Z",
          "key": "7007:24",
          "pid": 7007,
          "span": 24,
          "kind": "subprocess",
          "name": "gh api",
          "outcome": "failed",
          "dur_ms": 30006.4,
          "address": "20.172.24.160",
          "path": [
            {
              "key": "7007:22",
              "kind": "request",
              "name": "POST /api/plugin/github/pull-refresh"
            },
            {
              "key": "7007:23",
              "kind": "job",
              "name": "mirror_refresh.MirrorSession._pull_job"
            }
          ]
        }
      ]
    },
    {
      "cause": "server_error",
      "source": "cause",
      "count": 2,
      "kinds": {
        "job": 1,
        "subprocess": 1
      },
      "names": {
        "pull_files_refresh.refresh_files": 1,
        "gh api": 1
      },
      "first": "2026-11-19T22:02:01.328Z",
      "last": "2026-11-19T22:02:01.331Z",
      "message": "GitHub answered HTTP 503",
      "addresses": [],
      "examples": [
        {
          "ts": "2026-11-19T22:02:01.331Z",
          "key": "7007:39",
          "pid": 7007,
          "span": 39,
          "kind": "job",
          "name": "pull_files_refresh.refresh_files",
          "outcome": "failed",
          "dur_ms": 1330.6,
          "address": null,
          "path": [
            {
              "key": "7007:38",
              "kind": "request",
              "name": "POST /api/plugin/github/pull-refresh"
            }
          ]
        },
        {
          "ts": "2026-11-19T22:02:01.328Z",
          "key": "7007:41",
          "pid": 7007,
          "span": 41,
          "kind": "subprocess",
          "name": "gh api",
          "outcome": "failed",
          "dur_ms": 688.9,
          "address": null,
          "path": [
            {
              "key": "7007:38",
              "kind": "request",
              "name": "POST /api/plugin/github/pull-refresh"
            },
            {
              "key": "7007:39",
              "kind": "job",
              "name": "pull_files_refresh.refresh_files"
            }
          ]
        }
      ]
    }
  ],
  "probe": {
    "ts": "2026-11-19T22:01:02.051Z",
    "key": "7007:25",
    "span": 25,
    "timeout_s": 3.0,
    "via_proxy": false,
    "target": "api.github.com:443",
    "verdict": "connect_timeout",
    "dns_ms": 6.6,
    "addresses": [
      {
        "address": "20.172.24.160",
        "result": "timeout",
        "ms": 1993.0
      }
    ],
    "control": {
      "target": "captive.apple.com:80",
      "verdict": "reachable"
    },
    "cause": "connect_timeout",
    "message": "GitHub could not be reached because the connection to api.github.com at 20.172.24.160 timed out after 2 s; other sites are reachable"
  },
  "page_reports": {
    "count": 1,
    "outcomes": {
      "never_completed": 1
    },
    "names": {
      "fetch GET /api/plugin/github/pull-comparison": 1
    },
    "examples": [
      {
        "ts": "2026-11-19T22:03:50.000Z",
        "key": "7007@57",
        "pid": 7007,
        "client": "k3v9q2zx-90",
        "name": "fetch GET /api/plugin/github/pull-comparison",
        "outcome": "never_completed",
        "dur_ms": 30000.0,
        "status": null,
        "path": "/pull/615"
      }
    ]
  },
  "unfinished": {
    "total": 2,
    "shown": 2,
    "rows": [
      {
        "type": "span",
        "key": "7007:45",
        "kind": "job",
        "name": "comparison_cache.manifest",
        "start_ms": 199910.0,
        "dur_ms": null,
        "outcome": null,
        "state": "unfinished",
        "client": "k3v9q2zx-90",
        "pid": 7007,
        "span": 45,
        "parent": "7007:44",
        "attrs": {
          "key": "store 4922384 519dabc merge_base"
        },
        "elapsed_ms": 29993.0,
        "opens": 3,
        "path": [
          {
            "key": "7007:44",
            "kind": "request",
            "name": "GET /api/plugin/github/pull-comparison"
          }
        ]
      },
      {
        "type": "span",
        "key": "7007:46",
        "kind": "subprocess",
        "name": "git diff-tree",
        "start_ms": 199930.0,
        "dur_ms": null,
        "outcome": null,
        "state": "unfinished",
        "client": "k3v9q2zx-90",
        "pid": 7007,
        "span": 46,
        "parent": "7007:45",
        "attrs": {
          "args": [
            "diff-tree",
            "--raw",
            "-z",
            "4922384",
            "519dabc"
          ],
          "timeout_s": 900.0
        },
        "elapsed_ms": 29973.0,
        "opens": 2,
        "path": [
          {
            "key": "7007:44",
            "kind": "request",
            "name": "GET /api/plugin/github/pull-comparison"
          },
          {
            "key": "7007:45",
            "kind": "job",
            "name": "comparison_cache.manifest"
          }
        ]
      }
    ]
  },
  "not_failures": {
    "cancelled": 1
  }
}
? 0
```

## Test: a log that holds nothing to count

A segment a server has just opened holds one record and no spans, and its Errors say so.

```console
$ metab root --api '/api/plugin/event-log/errors?path=events-20261119T230000Z-p9-000.jsonl'
api: /api/plugin/event-log/errors?path=events-20261119T230000Z-p9-000.jsonl
status: 200
{
  "view": "errors",
  "log": {
    "schema_version": 1,
    "kinds": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcomes": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never_completed"
    ],
    "edges_ms": [
      1.0,
      10.0,
      100.0,
      500.0,
      2000.0,
      10000.0
    ],
    "bytes": 104,
    "records": 1,
    "skipped": 0,
    "spans": 0,
    "unfinished": 0,
    "started": "2026-11-19T23:00:00.000Z",
    "ended": "2026-11-19T23:00:00.000Z",
    "extent_ms": 0.0,
    "pids": [
      9
    ],
    "continues": false
  },
  "kinds": [],
  "failures": 0,
  "causes": [],
  "probe": null,
  "page_reports": {
    "count": 0,
    "outcomes": {},
    "names": {},
    "examples": []
  },
  "unfinished": {
    "total": 0,
    "shown": 0,
    "rows": []
  },
  "not_failures": {}
}
? 0
```

## Test: the roots newest first, and where a row is

`order=newest` lists the roots last first, for a person who comes to a long log for its
latest requests; what a span started stays in time order.
`focus` names a row by its key, and the answer’s `focus` gives each step from a root
down to it with its place among its parent’s rows, in this order and under this filter,
so a page can open each span above it at the page that holds the next.
A row the filter does not show, or the file does not hold, says so.

```console
$ metab root --api '/api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&order=newest&limit=1&focus=7007:25'
api: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&order=newest&limit=1&focus=7007:25
status: 200
{
  "view": "timeline",
  "log": {
    "schema_version": 1,
    "kinds": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcomes": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never_completed"
    ],
    "edges_ms": [
      1.0,
      10.0,
      100.0,
      500.0,
      2000.0,
      10000.0
    ],
    "bytes": 14917,
    "records": 58,
    "skipped": 2,
    "spans": 46,
    "unfinished": 2,
    "started": "2026-11-19T22:00:00.100Z",
    "ended": "2026-11-19T22:03:50.003Z",
    "extent_ms": 229903.0,
    "pids": [
      7007
    ],
    "continues": false
  },
  "query": {
    "kind": [],
    "outcome": [],
    "name": null,
    "client": null,
    "cause": null,
    "min_ms": null
  },
  "order": "newest",
  "parent": null,
  "total": 44,
  "offset": 0,
  "limit": 1,
  "max_limit": 1000,
  "has_more": true,
  "rows": [
    {
      "type": "report",
      "key": "7007@57",
      "kind": "browser",
      "name": "fetch GET /api/plugin/github/pull-comparison",
      "start_ms": 199900.0,
      "dur_ms": 30000.0,
      "outcome": "never_completed",
      "state": "report",
      "client": "k3v9q2zx-90",
      "pid": 7007,
      "span": null,
      "parent": null,
      "attrs": {
        "threshold_ms": 2000.0,
        "path": "/pull/615"
      },
      "elapsed_ms": 30000.0,
      "event": "end",
      "children": 0,
      "below": 0,
      "matched": true
    }
  ],
  "focus": {
    "key": "7007:25",
    "found": true,
    "steps": [
      {
        "parent": null,
        "key": "7007:22",
        "index": 21
      },
      {
        "parent": "7007:22",
        "key": "7007:23",
        "index": 0
      },
      {
        "parent": "7007:23",
        "key": "7007:25",
        "index": 1
      }
    ]
  }
}
? 0
```

```console
$ metab root --api '/api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&limit=1&focus=7007:25&kind=request'
api: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&limit=1&focus=7007:25&kind=request
status: 200
{
  "view": "timeline",
  "log": {
    "schema_version": 1,
    "kinds": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcomes": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never_completed"
    ],
    "edges_ms": [
      1.0,
      10.0,
      100.0,
      500.0,
      2000.0,
      10000.0
    ],
    "bytes": 14917,
    "records": 58,
    "skipped": 2,
    "spans": 46,
    "unfinished": 2,
    "started": "2026-11-19T22:00:00.100Z",
    "ended": "2026-11-19T22:03:50.003Z",
    "extent_ms": 229903.0,
    "pids": [
      7007
    ],
    "continues": false
  },
  "query": {
    "kind": [
      "request"
    ],
    "outcome": [],
    "name": null,
    "client": null,
    "cause": null,
    "min_ms": null
  },
  "order": "oldest",
  "parent": null,
  "total": 36,
  "offset": 0,
  "limit": 1,
  "max_limit": 1000,
  "has_more": true,
  "rows": [
    {
      "type": "span",
      "key": "7007:1",
      "kind": "request",
      "name": "GET /view/",
      "start_ms": 899.2,
      "dur_ms": 11.8,
      "outcome": "ok",
      "state": "ended",
      "client": "k3v9q2zx-1",
      "pid": 7007,
      "span": 1,
      "parent": null,
      "attrs": {
        "status": 200,
        "bytes": 4300,
        "start_ms": 11.5
      },
      "elapsed_ms": 11.8,
      "children": 0,
      "below": 0,
      "matched": true
    }
  ],
  "focus": {
    "key": "7007:25",
    "found": false,
    "reason": "filtered",
    "steps": []
  }
}
? 0
```

```console
$ metab root --api '/api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&limit=1&focus=7007:999'
api: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&limit=1&focus=7007:999
status: 200
{
  "view": "timeline",
  "log": {
    "schema_version": 1,
    "kinds": [
      "request",
      "job",
      "subprocess",
      "browser",
      "lifecycle",
      "loop",
      "probe"
    ],
    "outcomes": [
      "ok",
      "failed",
      "timeout",
      "cancelled",
      "abandoned",
      "never_completed"
    ],
    "edges_ms": [
      1.0,
      10.0,
      100.0,
      500.0,
      2000.0,
      10000.0
    ],
    "bytes": 14917,
    "records": 58,
    "skipped": 2,
    "spans": 46,
    "unfinished": 2,
    "started": "2026-11-19T22:00:00.100Z",
    "ended": "2026-11-19T22:03:50.003Z",
    "extent_ms": 229903.0,
    "pids": [
      7007
    ],
    "continues": false
  },
  "query": {
    "kind": [],
    "outcome": [],
    "name": null,
    "client": null,
    "cause": null,
    "min_ms": null
  },
  "order": "oldest",
  "parent": null,
  "total": 44,
  "offset": 0,
  "limit": 1,
  "max_limit": 1000,
  "has_more": true,
  "rows": [
    {
      "type": "mark",
      "key": "7007@1",
      "kind": "lifecycle",
      "name": "server.start",
      "start_ms": 0.0,
      "dur_ms": null,
      "outcome": null,
      "state": "mark",
      "client": null,
      "pid": 7007,
      "span": null,
      "parent": null,
      "attrs": {
        "served": "https://github.com/octo/demo",
        "version": "0.13.0"
      },
      "elapsed_ms": null,
      "children": 0,
      "below": 0,
      "matched": true
    }
  ],
  "focus": {
    "key": "7007:999",
    "found": false,
    "reason": "missing",
    "steps": []
  }
}
? 0
```

```console
$ metab root --api '/api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&order=sideways'
api: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&order=sideways
status: 400
{
  "error": "order must be one of oldest, newest; not sideways",
  "code": "invalid_query"
}
Error: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&order=sideways returned HTTP 400
? 1
```

## Test: what the routes refuse

```console
$ metab root --api '/api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&parent=7007:99'
api: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&parent=7007:99
status: 404
{
  "error": "no span 7007:99 in this log",
  "code": "span_missing"
}
Error: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&parent=7007:99 returned HTTP 404
? 1
```

```console
$ metab root --api '/api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&limit=0'
api: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&limit=0
status: 400
{
  "error": "limit must be from 1 to 1000",
  "code": "invalid_query"
}
Error: /api/plugin/event-log/timeline?path=events-20261119T220000Z-p7007-000.jsonl&limit=0 returned HTTP 400
? 1
```

```console
$ metab root --api '/api/plugin/event-log/kinds?path=events-20261119T220000Z-p7007-000.jsonl&kind=jobs'
api: /api/plugin/event-log/kinds?path=events-20261119T220000Z-p7007-000.jsonl&kind=jobs
status: 400
{
  "error": "kind must be among request, job, subprocess, browser, lifecycle, loop, probe; not jobs",
  "code": "invalid_query"
}
Error: /api/plugin/event-log/kinds?path=events-20261119T220000Z-p7007-000.jsonl&kind=jobs returned HTTP 400
? 1
```

```console
$ metab root --api '/api/plugin/event-log/slowest?path=events-20261119T220000Z-p7007-000.jsonl&bogus=1'
api: /api/plugin/event-log/slowest?path=events-20261119T220000Z-p7007-000.jsonl&bogus=1
status: 400
{
  "error": "unknown parameter bogus",
  "code": "invalid_query"
}
Error: /api/plugin/event-log/slowest?path=events-20261119T220000Z-p7007-000.jsonl&bogus=1 returned HTTP 400
? 1
```

```console
$ metab root --api '/api/plugin/event-log/errors?path=absent.jsonl'
api: /api/plugin/event-log/errors?path=absent.jsonl
status: 404
{
  "error": "Not found",
  "code": "not_found"
}
Error: /api/plugin/event-log/errors?path=absent.jsonl returned HTTP 404
? 1
```

```console
$ metab root --api '/api/plugin/event-log/errors?path=events.jsonl'
api: /api/plugin/event-log/errors?path=events.jsonl
status: 415
{
  "error": "None of its 2 lines is an event log record of schema version 1",
  "code": "not_an_event_log"
}
Error: /api/plugin/event-log/errors?path=events.jsonl returned HTTP 415
? 1
```
