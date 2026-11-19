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
  install -m 600
  "$TRYSCRIPT_TEST_DIR/../fixtures/event-log-failures/events-20261119T213500Z-p5151-000.jsonl"
  state/events/ &&
  touch -t 202611192144.00 state/events/events-20261119T213500Z-p5151-000.jsonl
---
# Golden tests: recent GitHub failures and their causes, through `--api`

`/api/event-log/failures` counts the failures in the structured event log since a
moment, grouped by cause: the vocabulary `metabrowser.network_cause` gives gh’s and
Git’s errors alike. The fixture segment is a server on a network whose DNS answered
`api.github.com` with an address the network could not connect to, as the owner’s
machine did on 2026-11-19: a `gh` call that timed out connecting to `20.172.24.160`, the
probe that followed it (the name resolved, the connection timed out, and another site
was reachable), the refresh job that failed on it, a Git fetch that could not connect, a
`gh auth status` that never answered while the probe found GitHub reachable, and a list
refresh GitHub answered with HTTP 503. One failure, before the window opens, is not
counted.

## Test: the failures in the window, by cause, most frequent first

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log/failures?since=2026-11-19T21:00:00Z'
api: /api/event-log/failures?since=2026-11-19T21:00:00Z
status: 200
{
  "schema_version": 1,
  "directory": "[CWD]/state/events",
  "state": "present",
  "since": "2026-11-19T21:00:00Z",
  "until": null,
  "kinds": [],
  "files": [
    "events-20261119T213500Z-p5151-000.jsonl"
  ],
  "scanned": 11,
  "failures": 7,
  "causes": [
    {
      "cause": "connect_timeout",
      "source": "cause",
      "count": 4,
      "kinds": {
        "subprocess": 2,
        "probe": 1,
        "job": 1
      },
      "names": {
        "gh api": 1,
        "probe api.github.com:443": 1,
        "pull_files_refresh.refresh_files": 1,
        "git fetch": 1
      },
      "first": "2026-11-19T21:40:32.322Z",
      "last": "2026-11-19T21:41:10.502Z",
      "message": "Couldn't connect to GitHub (api.github.com at 20.172.24.160): the connection timed out after 3 s; other sites are reachable",
      "addresses": [
        "20.172.24.160"
      ],
      "examples": [
        {
          "ts": "2026-11-19T21:41:10.502Z",
          "file": "events-20261119T213500Z-p5151-000.jsonl",
          "span": 16,
          "kind": "subprocess",
          "name": "git fetch",
          "outcome": "failed",
          "dur_ms": 75011.8,
          "address": null,
          "details": "/api/event-log?file=events-20261119T213500Z-p5151-000.jsonl&span=16"
        },
        {
          "ts": "2026-11-19T21:40:35.336Z",
          "file": "events-20261119T213500Z-p5151-000.jsonl",
          "span": 12,
          "kind": "job",
          "name": "pull_files_refresh.refresh_files",
          "outcome": "failed",
          "dur_ms": 33026.1,
          "address": null,
          "details": "/api/event-log?file=events-20261119T213500Z-p5151-000.jsonl&span=12"
        },
        {
          "ts": "2026-11-19T21:40:35.330Z",
          "file": "events-20261119T213500Z-p5151-000.jsonl",
          "span": 14,
          "kind": "probe",
          "name": "probe api.github.com:443",
          "outcome": "failed",
          "dur_ms": 3006.9,
          "address": null,
          "details": "/api/event-log?file=events-20261119T213500Z-p5151-000.jsonl&span=14"
        }
      ]
    },
    {
      "cause": "no_answer",
      "source": "cause",
      "count": 2,
      "kinds": {
        "subprocess": 1,
        "job": 1
      },
      "names": {
        "gh auth": 1,
        "pull_cores.refresh_core": 1
      },
      "first": "2026-11-19T21:42:20.880Z",
      "last": "2026-11-19T21:42:20.991Z",
      "message": "gh did not answer within 15 s, although api.github.com (140.82.114.5) accepted a connection in 38 ms",
      "addresses": [],
      "examples": [
        {
          "ts": "2026-11-19T21:42:20.991Z",
          "file": "events-20261119T213500Z-p5151-000.jsonl",
          "span": 17,
          "kind": "job",
          "name": "pull_cores.refresh_core",
          "outcome": "failed",
          "dur_ms": 15121.7,
          "address": null,
          "details": "/api/event-log?file=events-20261119T213500Z-p5151-000.jsonl&span=17"
        },
        {
          "ts": "2026-11-19T21:42:20.880Z",
          "file": "events-20261119T213500Z-p5151-000.jsonl",
          "span": 18,
          "kind": "subprocess",
          "name": "gh auth",
          "outcome": "timeout",
          "dur_ms": 15003.0,
          "address": null,
          "details": "/api/event-log?file=events-20261119T213500Z-p5151-000.jsonl&span=18"
        }
      ]
    },
    {
      "cause": "server_error",
      "source": "cause",
      "count": 1,
      "kinds": {
        "job": 1
      },
      "names": {
        "pull_list_refresh.refresh_list": 1
      },
      "first": "2026-11-19T21:43:05.114Z",
      "last": "2026-11-19T21:43:05.114Z",
      "message": "GitHub answered HTTP 503",
      "addresses": [],
      "examples": [
        {
          "ts": "2026-11-19T21:43:05.114Z",
          "file": "events-20261119T213500Z-p5151-000.jsonl",
          "span": 19,
          "kind": "job",
          "name": "pull_list_refresh.refresh_list",
          "outcome": "failed",
          "dur_ms": 612.4,
          "address": null,
          "details": "/api/event-log?file=events-20261119T213500Z-p5151-000.jsonl&span=19"
        }
      ]
    }
  ],
  "probe": {
    "ts": "2026-11-19T21:40:35.330Z",
    "file": "events-20261119T213500Z-p5151-000.jsonl",
    "span": 14,
    "timeout_s": 3.0,
    "via_proxy": false,
    "target": "api.github.com:443",
    "verdict": "connect_timeout",
    "dns_ms": 6.6,
    "addresses": [
      {
        "address": "20.172.24.160",
        "result": "timeout",
        "ms": 3000.4
      }
    ],
    "probed_at": "2026-11-19T21:40:35Z",
    "control": {
      "target": "captive.apple.com:80",
      "verdict": "reachable"
    },
    "cause": "connect_timeout",
    "message": "Couldn't connect to GitHub (api.github.com at 20.172.24.160): the connection timed out after 3 s; other sites are reachable"
  }
}
? 0
```

## Test: only processes, one record per failed gh or git call

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log/failures?since=2026-11-19T21:00:00Z&kind=subprocess'
api: /api/event-log/failures?since=2026-11-19T21:00:00Z&kind=subprocess
status: 200
{
  "schema_version": 1,
  "directory": "[CWD]/state/events",
  "state": "present",
  "since": "2026-11-19T21:00:00Z",
  "until": null,
  "kinds": [
    "subprocess"
  ],
  "files": [
    "events-20261119T213500Z-p5151-000.jsonl"
  ],
  "scanned": 11,
  "failures": 3,
  "causes": [
    {
      "cause": "connect_timeout",
      "source": "cause",
      "count": 2,
      "kinds": {
        "subprocess": 2
      },
      "names": {
        "gh api": 1,
        "git fetch": 1
      },
      "first": "2026-11-19T21:40:32.322Z",
      "last": "2026-11-19T21:41:10.502Z",
      "message": "fatal: unable to access 'https://github.com/octo/demo.git/': Failed to connect to github.com port 443 after 75003 ms: Connection timed out",
      "addresses": [
        "20.172.24.160"
      ],
      "examples": [
        {
          "ts": "2026-11-19T21:41:10.502Z",
          "file": "events-20261119T213500Z-p5151-000.jsonl",
          "span": 16,
          "kind": "subprocess",
          "name": "git fetch",
          "outcome": "failed",
          "dur_ms": 75011.8,
          "address": null,
          "details": "/api/event-log?file=events-20261119T213500Z-p5151-000.jsonl&span=16"
        },
        {
          "ts": "2026-11-19T21:40:32.322Z",
          "file": "events-20261119T213500Z-p5151-000.jsonl",
          "span": 13,
          "kind": "subprocess",
          "name": "gh api",
          "outcome": "failed",
          "dur_ms": 30006.4,
          "address": "20.172.24.160",
          "details": "/api/event-log?file=events-20261119T213500Z-p5151-000.jsonl&span=13"
        }
      ]
    },
    {
      "cause": "no_answer",
      "source": "cause",
      "count": 1,
      "kinds": {
        "subprocess": 1
      },
      "names": {
        "gh auth": 1
      },
      "first": "2026-11-19T21:42:20.880Z",
      "last": "2026-11-19T21:42:20.880Z",
      "message": "timed out before any answer",
      "addresses": [],
      "examples": [
        {
          "ts": "2026-11-19T21:42:20.880Z",
          "file": "events-20261119T213500Z-p5151-000.jsonl",
          "span": 18,
          "kind": "subprocess",
          "name": "gh auth",
          "outcome": "timeout",
          "dur_ms": 15003.0,
          "address": null,
          "details": "/api/event-log?file=events-20261119T213500Z-p5151-000.jsonl&span=18"
        }
      ]
    }
  ],
  "probe": {
    "ts": "2026-11-19T21:40:35.330Z",
    "file": "events-20261119T213500Z-p5151-000.jsonl",
    "span": 14,
    "timeout_s": 3.0,
    "via_proxy": false,
    "target": "api.github.com:443",
    "verdict": "connect_timeout",
    "dns_ms": 6.6,
    "addresses": [
      {
        "address": "20.172.24.160",
        "result": "timeout",
        "ms": 3000.4
      }
    ],
    "probed_at": "2026-11-19T21:40:35Z",
    "control": {
      "target": "captive.apple.com:80",
      "verdict": "reachable"
    },
    "cause": "connect_timeout",
    "message": "Couldn't connect to GitHub (api.github.com at 20.172.24.160): the connection timed out after 3 s; other sites are reachable"
  }
}
? 0
```

## Test: a window that closes before the later failures

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log/failures?since=2026-11-19T21:00:00Z&until=2026-11-19T21:41:00Z&kind=job'
api: /api/event-log/failures?since=2026-11-19T21:00:00Z&until=2026-11-19T21:41:00Z&kind=job
status: 200
{
  "schema_version": 1,
  "directory": "[CWD]/state/events",
  "state": "present",
  "since": "2026-11-19T21:00:00Z",
  "until": "2026-11-19T21:41:00Z",
  "kinds": [
    "job"
  ],
  "files": [
    "events-20261119T213500Z-p5151-000.jsonl"
  ],
  "scanned": 11,
  "failures": 1,
  "causes": [
    {
      "cause": "connect_timeout",
      "source": "cause",
      "count": 1,
      "kinds": {
        "job": 1
      },
      "names": {
        "pull_files_refresh.refresh_files": 1
      },
      "first": "2026-11-19T21:40:35.336Z",
      "last": "2026-11-19T21:40:35.336Z",
      "message": "Couldn't connect to GitHub (api.github.com at 20.172.24.160): the connection timed out after 3 s; other sites are reachable",
      "addresses": [],
      "examples": [
        {
          "ts": "2026-11-19T21:40:35.336Z",
          "file": "events-20261119T213500Z-p5151-000.jsonl",
          "span": 12,
          "kind": "job",
          "name": "pull_files_refresh.refresh_files",
          "outcome": "failed",
          "dur_ms": 33026.1,
          "address": null,
          "details": "/api/event-log?file=events-20261119T213500Z-p5151-000.jsonl&span=12"
        }
      ]
    }
  ],
  "probe": {
    "ts": "2026-11-19T21:40:35.330Z",
    "file": "events-20261119T213500Z-p5151-000.jsonl",
    "span": 14,
    "timeout_s": 3.0,
    "via_proxy": false,
    "target": "api.github.com:443",
    "verdict": "connect_timeout",
    "dns_ms": 6.6,
    "addresses": [
      {
        "address": "20.172.24.160",
        "result": "timeout",
        "ms": 3000.4
      }
    ],
    "probed_at": "2026-11-19T21:40:35Z",
    "control": {
      "target": "captive.apple.com:80",
      "verdict": "reachable"
    },
    "cause": "connect_timeout",
    "message": "Couldn't connect to GitHub (api.github.com at 20.172.24.160): the connection timed out after 3 s; other sites are reachable"
  }
}
? 0
```

## Test: the records of one cause, newest first

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log?cause=connect_timeout&event=end'
api: /api/event-log?cause=connect_timeout&event=end
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
      "name": "events-20261119T213500Z-p5151-000.jsonl",
      "bytes": 4041,
      "modified": "2026-11-19T21:44:00Z",
      "pid": 5151,
      "started": "20261119T213500Z",
      "segment": 0
    }
  ],
  "query": {
    "file": null,
    "kind": [],
    "outcome": [],
    "event": [
      "end"
    ],
    "name": null,
    "client": null,
    "cause": "connect_timeout",
    "span": null,
    "min_ms": null,
    "sort": "time",
    "limit": 100
  },
  "file": "events-20261119T213500Z-p5151-000.jsonl",
  "scanned": 11,
  "matched": 4,
  "events": [
    {
      "v": 1,
      "ts": "2026-11-19T21:41:10.502Z",
      "event": "end",
      "kind": "subprocess",
      "name": "git fetch",
      "span": 16,
      "parent": 15,
      "dur_ms": 75011.8,
      "outcome": "failed",
      "pid": 5151,
      "attrs": {
        "args": [
          "fetch",
          "--prune",
          "--",
          "https://github.com/octo/demo.git"
        ],
        "exit": 128,
        "stderr_tail": "fatal: unable to access 'https://github.com/octo/demo.git/': Failed to connect to github.com port 443 after 75003 ms: Connection timed out",
        "cause": "connect_timeout"
      }
    },
    {
      "v": 1,
      "ts": "2026-11-19T21:40:35.336Z",
      "event": "end",
      "kind": "job",
      "name": "pull_files_refresh.refresh_files",
      "span": 12,
      "parent": 11,
      "dur_ms": 33026.1,
      "outcome": "failed",
      "pid": 5151,
      "attrs": {
        "key": "demo:files/615",
        "network": true,
        "queued_ms": 0.2,
        "cause": "connect_timeout",
        "failure": "network_error",
        "failure_message": "Couldn't connect to GitHub (api.github.com at 20.172.24.160): the connection timed out after 3 s; other sites are reachable"
      }
    },
    {
      "v": 1,
      "ts": "2026-11-19T21:40:35.330Z",
      "event": "end",
      "kind": "probe",
      "name": "probe api.github.com:443",
      "span": 14,
      "parent": 12,
      "dur_ms": 3006.9,
      "outcome": "failed",
      "pid": 5151,
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
            "ms": 3000.4
          }
        ],
        "probed_at": "2026-11-19T21:40:35Z",
        "control": {
          "target": "captive.apple.com:80",
          "verdict": "reachable"
        },
        "cause": "connect_timeout",
        "message": "Couldn't connect to GitHub (api.github.com at 20.172.24.160): the connection timed out after 3 s; other sites are reachable"
      }
    },
    {
      "v": 1,
      "ts": "2026-11-19T21:40:32.322Z",
      "event": "end",
      "kind": "subprocess",
      "name": "gh api",
      "span": 13,
      "parent": 12,
      "dur_ms": 30006.4,
      "outcome": "failed",
      "pid": 5151,
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
      }
    }
  ],
  "open": []
}
? 0
```

## Test: a moment the route cannot read is refused

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log/failures?since=yesterday'
api: /api/event-log/failures?since=yesterday
status: 400
{
  "error": "since must be a UTC time such as 2026-11-19T21:00:00Z",
  "code": "invalid_query"
}
Error: /api/event-log/failures?since=yesterday returned HTTP 400
? 1
```
