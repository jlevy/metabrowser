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
  install -d -m 700 state state/events &&
  install -m 600 "$TRYSCRIPT_TEST_DIR/../fixtures/event-log/events-20261119T210201Z-p4242-000.jsonl"
  "$TRYSCRIPT_TEST_DIR/../fixtures/event-log/events-20261118T090000Z-p17-000.jsonl"
  state/events/ &&
  touch -t 202611192103.41 state/events/events-20261119T210201Z-p4242-000.jsonl &&
  touch -t 202611180901.00 state/events/events-20261118T090000Z-p17-000.jsonl
---
# Golden tests: the event log through `--api`

`/api/event-log` reads the structured event log that a served process writes to the
state directory (`metabrowser.event_log`): where it is, the segments in it, and their
records, filtered and sorted.
A one-shot command writes no log of its own, so `writing` is `null` and nothing is
`open`; the route reads what servers wrote.

The newer fixture segment is the record a stuck pull request page leaves: a refresh job
whose `gh auth status` never answered and timed out at 15 s, then a comparison listing
that started, was reported open at 2, 4, and 8 s, and never ended before the server was
killed mid-line. The older segment is a slow tree request from another server.
The torn last line and a line of a later schema version are skipped.

Each command names its state directory with `METABROWSER_STATE_DIR`, because the route
resolves it per request.

## Test: the newest segment, newest record first

`limit` keeps the answer short; `matched` says how many records the filters let through.

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log?limit=2'
api: /api/event-log?limit=2
status: 200
{
  "schema_version": 1,
  "directory": "[CWD]/state/events",
  "state": "present",
  "writing": null,
  "bounds": {
    "max_file_bytes": 2097152,
    "max_total_bytes": 33554432,
    "max_line_bytes": 8192,
    "open_after_ms": 2000.0
  },
  "files": [
    {
      "name": "events-20261119T210201Z-p4242-000.jsonl",
      "bytes": 3130,
      "modified": "2026-11-19T21:03:41Z",
      "pid": 4242,
      "started": "20261119T210201Z",
      "segment": 0
    },
    {
      "name": "events-20261118T090000Z-p17-000.jsonl",
      "bytes": 497,
      "modified": "2026-11-18T09:01:00Z",
      "pid": 17,
      "started": "20261118T090000Z",
      "segment": 0
    }
  ],
  "query": {
    "file": null,
    "kind": [],
    "outcome": [],
    "event": [],
    "name": null,
    "client": null,
    "span": null,
    "min_ms": null,
    "sort": "time",
    "limit": 2
  },
  "file": "events-20261119T210201Z-p4242-000.jsonl",
  "scanned": 13,
  "matched": 13,
  "events": [
    {
      "v": 1,
      "ts": "2026-11-19T21:03:40.515Z",
      "event": "end",
      "kind": "request",
      "name": "GET /api/plugin/github/pull-comparison",
      "span": 11,
      "dur_ms": 30003.1,
      "outcome": "cancelled",
      "pid": 4242,
      "attrs": {
        "status": null,
        "bytes": 0,
        "query": "number=615&left=4922384&right=519dabc&base_policy=merge_base"
      }
    },
    {
      "v": 1,
      "ts": "2026-11-19T21:03:18.540Z",
      "event": "open",
      "kind": "job",
      "name": "comparison_cache.manifest",
      "span": 12,
      "parent": 11,
      "dur_ms": 8028.4,
      "pid": 4242,
      "attrs": {
        "key": "store 4922384 519dabc merge_base"
      }
    }
  ],
  "open": []
}
? 0
```

## Test: what failed or timed out

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log?outcome=timeout,failed'
api: /api/event-log?outcome=timeout,failed
status: 200
{
  "schema_version": 1,
  "directory": "[CWD]/state/events",
  "state": "present",
  "writing": null,
  "bounds": {
    "max_file_bytes": 2097152,
    "max_total_bytes": 33554432,
    "max_line_bytes": 8192,
    "open_after_ms": 2000.0
  },
  "files": [
    {
      "name": "events-20261119T210201Z-p4242-000.jsonl",
      "bytes": 3130,
      "modified": "2026-11-19T21:03:41Z",
      "pid": 4242,
      "started": "20261119T210201Z",
      "segment": 0
    },
    {
      "name": "events-20261118T090000Z-p17-000.jsonl",
      "bytes": 497,
      "modified": "2026-11-18T09:01:00Z",
      "pid": 17,
      "started": "20261118T090000Z",
      "segment": 0
    }
  ],
  "query": {
    "file": null,
    "kind": [],
    "outcome": [
      "timeout",
      "failed"
    ],
    "event": [],
    "name": null,
    "client": null,
    "span": null,
    "min_ms": null,
    "sort": "time",
    "limit": 100
  },
  "file": "events-20261119T210201Z-p4242-000.jsonl",
  "scanned": 13,
  "matched": 2,
  "events": [
    {
      "v": 1,
      "ts": "2026-11-19T21:02:49.801Z",
      "event": "end",
      "kind": "job",
      "name": "mirror_refresh.MirrorSession._pull_job",
      "span": 8,
      "parent": 7,
      "dur_ms": 15045.2,
      "outcome": "failed",
      "pid": 4242,
      "attrs": {
        "key": "demo:pull/615",
        "network": false,
        "failure": "network_error",
        "failure_message": "gh did not answer within 15 s"
      }
    },
    {
      "v": 1,
      "ts": "2026-11-19T21:02:49.764Z",
      "event": "end",
      "kind": "subprocess",
      "name": "gh auth",
      "span": 9,
      "parent": 8,
      "dur_ms": 15007.8,
      "outcome": "timeout",
      "pid": 4242,
      "attrs": {
        "args": [
          "auth",
          "status",
          "--active",
          "--hostname",
          "github.com",
          "--json",
          "hosts"
        ],
        "timeout_s": 15.0,
        "stdout_bytes": 0,
        "stderr_tail": "",
        "stalled": "before any answer"
      }
    }
  ],
  "open": []
}
? 0
```

## Test: one job and the work it started

`span` names a span; the answer holds its records and those of the spans it started,
here the refresh job and the `gh` process it waited on.

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log?span=8&event=start,end'
api: /api/event-log?span=8&event=start,end
status: 200
{
  "schema_version": 1,
  "directory": "[CWD]/state/events",
  "state": "present",
  "writing": null,
  "bounds": {
    "max_file_bytes": 2097152,
    "max_total_bytes": 33554432,
    "max_line_bytes": 8192,
    "open_after_ms": 2000.0
  },
  "files": [
    {
      "name": "events-20261119T210201Z-p4242-000.jsonl",
      "bytes": 3130,
      "modified": "2026-11-19T21:03:41Z",
      "pid": 4242,
      "started": "20261119T210201Z",
      "segment": 0
    },
    {
      "name": "events-20261118T090000Z-p17-000.jsonl",
      "bytes": 497,
      "modified": "2026-11-18T09:01:00Z",
      "pid": 17,
      "started": "20261118T090000Z",
      "segment": 0
    }
  ],
  "query": {
    "file": null,
    "kind": [],
    "outcome": [],
    "event": [
      "start",
      "end"
    ],
    "name": null,
    "client": null,
    "span": 8,
    "min_ms": null,
    "sort": "time",
    "limit": 100
  },
  "file": "events-20261119T210201Z-p4242-000.jsonl",
  "scanned": 13,
  "matched": 3,
  "events": [
    {
      "v": 1,
      "ts": "2026-11-19T21:02:49.801Z",
      "event": "end",
      "kind": "job",
      "name": "mirror_refresh.MirrorSession._pull_job",
      "span": 8,
      "parent": 7,
      "dur_ms": 15045.2,
      "outcome": "failed",
      "pid": 4242,
      "attrs": {
        "key": "demo:pull/615",
        "network": false,
        "failure": "network_error",
        "failure_message": "gh did not answer within 15 s"
      }
    },
    {
      "v": 1,
      "ts": "2026-11-19T21:02:49.764Z",
      "event": "end",
      "kind": "subprocess",
      "name": "gh auth",
      "span": 9,
      "parent": 8,
      "dur_ms": 15007.8,
      "outcome": "timeout",
      "pid": 4242,
      "attrs": {
        "args": [
          "auth",
          "status",
          "--active",
          "--hostname",
          "github.com",
          "--json",
          "hosts"
        ],
        "timeout_s": 15.0,
        "stdout_bytes": 0,
        "stderr_tail": "",
        "stalled": "before any answer"
      }
    },
    {
      "v": 1,
      "ts": "2026-11-19T21:02:34.756Z",
      "event": "start",
      "kind": "job",
      "name": "mirror_refresh.MirrorSession._pull_job",
      "span": 8,
      "parent": 7,
      "pid": 4242,
      "attrs": {
        "key": "demo:pull/615",
        "network": false
      }
    }
  ],
  "open": []
}
? 0
```

## Test: a job that started and never ended

A start with open records and no end is work that was still running when the log
stopped.

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log?name=comparison_cache&event=start,open'
api: /api/event-log?name=comparison_cache&event=start,open
status: 200
{
  "schema_version": 1,
  "directory": "[CWD]/state/events",
  "state": "present",
  "writing": null,
  "bounds": {
    "max_file_bytes": 2097152,
    "max_total_bytes": 33554432,
    "max_line_bytes": 8192,
    "open_after_ms": 2000.0
  },
  "files": [
    {
      "name": "events-20261119T210201Z-p4242-000.jsonl",
      "bytes": 3130,
      "modified": "2026-11-19T21:03:41Z",
      "pid": 4242,
      "started": "20261119T210201Z",
      "segment": 0
    },
    {
      "name": "events-20261118T090000Z-p17-000.jsonl",
      "bytes": 497,
      "modified": "2026-11-18T09:01:00Z",
      "pid": 17,
      "started": "20261118T090000Z",
      "segment": 0
    }
  ],
  "query": {
    "file": null,
    "kind": [],
    "outcome": [],
    "event": [
      "start",
      "open"
    ],
    "name": "comparison_cache",
    "client": null,
    "span": null,
    "min_ms": null,
    "sort": "time",
    "limit": 100
  },
  "file": "events-20261119T210201Z-p4242-000.jsonl",
  "scanned": 13,
  "matched": 4,
  "events": [
    {
      "v": 1,
      "ts": "2026-11-19T21:03:18.540Z",
      "event": "open",
      "kind": "job",
      "name": "comparison_cache.manifest",
      "span": 12,
      "parent": 11,
      "dur_ms": 8028.4,
      "pid": 4242,
      "attrs": {
        "key": "store 4922384 519dabc merge_base"
      }
    },
    {
      "v": 1,
      "ts": "2026-11-19T21:03:14.530Z",
      "event": "open",
      "kind": "job",
      "name": "comparison_cache.manifest",
      "span": 12,
      "parent": 11,
      "dur_ms": 4018.2,
      "pid": 4242,
      "attrs": {
        "key": "store 4922384 519dabc merge_base"
      }
    },
    {
      "v": 1,
      "ts": "2026-11-19T21:03:12.520Z",
      "event": "open",
      "kind": "job",
      "name": "comparison_cache.manifest",
      "span": 12,
      "parent": 11,
      "dur_ms": 2008.0,
      "pid": 4242,
      "attrs": {
        "key": "store 4922384 519dabc merge_base"
      }
    },
    {
      "v": 1,
      "ts": "2026-11-19T21:03:10.512Z",
      "event": "start",
      "kind": "job",
      "name": "comparison_cache.manifest",
      "span": 12,
      "parent": 11,
      "pid": 4242,
      "attrs": {
        "key": "store 4922384 519dabc merge_base"
      }
    }
  ],
  "open": []
}
? 0
```

## Test: the slowest records of another segment

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log?file=events-20261118T090000Z-p17-000.jsonl&sort=duration&min_ms=1000'
api: /api/event-log?file=events-20261118T090000Z-p17-000.jsonl&sort=duration&min_ms=1000
status: 200
{
  "schema_version": 1,
  "directory": "[CWD]/state/events",
  "state": "present",
  "writing": null,
  "bounds": {
    "max_file_bytes": 2097152,
    "max_total_bytes": 33554432,
    "max_line_bytes": 8192,
    "open_after_ms": 2000.0
  },
  "files": [
    {
      "name": "events-20261119T210201Z-p4242-000.jsonl",
      "bytes": 3130,
      "modified": "2026-11-19T21:03:41Z",
      "pid": 4242,
      "started": "20261119T210201Z",
      "segment": 0
    },
    {
      "name": "events-20261118T090000Z-p17-000.jsonl",
      "bytes": 497,
      "modified": "2026-11-18T09:01:00Z",
      "pid": 17,
      "started": "20261118T090000Z",
      "segment": 0
    }
  ],
  "query": {
    "file": "events-20261118T090000Z-p17-000.jsonl",
    "kind": [],
    "outcome": [],
    "event": [],
    "name": null,
    "client": null,
    "span": null,
    "min_ms": 1000.0,
    "sort": "duration",
    "limit": 100
  },
  "file": "events-20261118T090000Z-p17-000.jsonl",
  "scanned": 3,
  "matched": 1,
  "events": [
    {
      "v": 1,
      "ts": "2026-11-18T09:00:04.800Z",
      "event": "end",
      "kind": "request",
      "name": "GET /api/tree",
      "span": 3,
      "dur_ms": 2412.5,
      "outcome": "ok",
      "pid": 17,
      "attrs": {
        "status": 200,
        "bytes": 51200,
        "start_ms": 2410.0,
        "phases": {
          "read": 2380.2,
          "encode": 12.1
        }
      }
    }
  ],
  "open": []
}
? 0
```

## Test: a state directory with no log is an answer, not an error

```console
$ METABROWSER_STATE_DIR=$PWD/missing metab root --api '/api/event-log?limit=1'
api: /api/event-log?limit=1
status: 200
{
  "schema_version": 1,
  "directory": "[CWD]/missing/events",
  "state": "absent",
  "writing": null,
  "bounds": {
    "max_file_bytes": 2097152,
    "max_total_bytes": 33554432,
    "max_line_bytes": 8192,
    "open_after_ms": 2000.0
  },
  "files": [],
  "query": {
    "file": null,
    "kind": [],
    "outcome": [],
    "event": [],
    "name": null,
    "client": null,
    "span": null,
    "min_ms": null,
    "sort": "time",
    "limit": 1
  },
  "file": null,
  "scanned": 0,
  "matched": 0,
  "events": [],
  "open": []
}
? 0
```

## Test: a filter the route cannot apply is refused

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log?kind=jobs'
api: /api/event-log?kind=jobs
status: 400
{
  "error": "kind must be among request, job, subprocess, browser, lifecycle, loop, probe; not jobs",
  "code": "invalid_query"
}
Error: /api/event-log?kind=jobs returned HTTP 400
? 1
```

## Test: a segment the directory does not hold is not found

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log?file=events-20200101T000000Z-p1-000.jsonl'
api: /api/event-log?file=events-20200101T000000Z-p1-000.jsonl
status: 404
{
  "error": "no segment named events-20200101T000000Z-p1-000.jsonl",
  "code": "event_log_file_missing"
}
Error: /api/event-log?file=events-20200101T000000Z-p1-000.jsonl returned HTTP 404
? 1
```
