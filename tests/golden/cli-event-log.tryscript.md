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
patterns:
  ROOT_ARG: '\[ROOT\]'
before: >-
  install -d -m 700 state state/events &&
  install -m 600 "$TRYSCRIPT_TEST_DIR/../fixtures/event-log/events-20261119T210201Z-p4242-000.jsonl"
  "$TRYSCRIPT_TEST_DIR/../fixtures/event-log/events-20261118T090000Z-p17-000.jsonl"
  state/events/ &&
  touch -t 202611192103.41 state/events/events-20261119T210201Z-p4242-000.jsonl &&
  touch -t 202611180901.00 state/events/events-20261118T090000Z-p17-000.jsonl
---
# Golden tests: `--event-log`, Metabrowser’s own event log as ROOT

A served `metab` writes its event log to `events/` under the state directory
(`METABROWSER_STATE_DIR`, else `$XDG_STATE_HOME/metabrowser`, else
`~/.local/state/metabrowser`), and the event-log plugin opens a segment of it as spans
and latencies. `--event-log` names that directory as ROOT, so every mode that takes a
folder reads the log without the person finding the directory first: serving opens it at
its newest segment (`tests/test_cli_event_log.py` holds what serving is handed), `--api`
and `--show` read it as any folder, and a person who has no log yet is told where one is
written.

## Test: the segments are the folder’s files

```console
$ METABROWSER_STATE_DIR=$PWD/state metab --event-log --api /api/tree
api: /api/tree
status: 200
{
  "root": "<ROOT>",
  "tree": [
    {
      "name": "events-20261118T090000Z-p17-000.jsonl",
      "path": "events-20261118T090000Z-p17-000.jsonl",
      "type": "file",
      "size": 497,
      "mtime": 1794992460.0,
      "ext": ".jsonl"
    },
    {
      "name": "events-20261119T210201Z-p4242-000.jsonl",
      "path": "events-20261119T210201Z-p4242-000.jsonl",
      "type": "file",
      "size": 3130,
      "mtime": 1795122221.0,
      "ext": ".jsonl"
    }
  ],
  "filtered": null,
  "tally_cache_status": "done",
  "tally_cache_max_files": 500000,
  "summary": null,
  "file_type_registry": null,
  "extensions": null,
  "canonical_extensions": null,
  "type_families": null,
  "type_presets": null,
  "recency_tallies": null
}
? 0
```

## Test: a segment is an event log, with its views

```console
$ METABROWSER_STATE_DIR=$PWD/state metab --event-log --show events-20261119T210201Z-p4242-000.jsonl
show: events-20261119T210201Z-p4242-000.jsonl
route: /view/events-20261119T210201Z-p4242-000.jsonl
kind: event-log
views: timeline (default, key V), latency (key L), kinds (key B), errors (key E), raw (key S)
model: jsonl envelope; size=3130
? 0
```

## Test: the views are read the same way, through the folder

The newer segment is the record of a stuck pull request page; its Errors say what never
ended.

```console
$ METABROWSER_STATE_DIR=$PWD/state metab --event-log --api '/api/plugin/event-log/errors?path=events-20261119T210201Z-p4242-000.jsonl&kind=job'
api: /api/plugin/event-log/errors?path=events-20261119T210201Z-p4242-000.jsonl&kind=job
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
    "bytes": 3130,
    "records": 13,
    "skipped": 2,
    "spans": 6,
    "unfinished": 1,
    "started": "2026-11-19T21:02:01.981Z",
    "ended": "2026-11-19T21:03:40.515Z",
    "extent_ms": 98534.0,
    "pids": [
      4242
    ],
    "continues": false
  },
  "kinds": [
    "job"
  ],
  "failures": 1,
  "causes": [
    {
      "cause": "network_error",
      "source": "state",
      "count": 1,
      "kinds": {
        "job": 1
      },
      "names": {
        "mirror_refresh.MirrorSession._pull_job": 1
      },
      "first": "2026-11-19T21:02:49.801Z",
      "last": "2026-11-19T21:02:49.801Z",
      "message": "gh did not answer within 15 s",
      "addresses": [],
      "examples": [
        {
          "ts": "2026-11-19T21:02:49.801Z",
          "key": "4242:8",
          "pid": 4242,
          "span": 8,
          "kind": "job",
          "name": "mirror_refresh.MirrorSession._pull_job",
          "outcome": "failed",
          "dur_ms": 15045.2,
          "address": null,
          "path": [
            {
              "key": "4242:7",
              "kind": "request",
              "name": "POST /api/plugin/github/pull-refresh"
            }
          ]
        }
      ]
    }
  ],
  "probe": null,
  "page_reports": {
    "count": 0,
    "outcomes": {},
    "names": {},
    "examples": []
  },
  "unfinished": {
    "total": 1,
    "shown": 1,
    "rows": [
      {
        "type": "span",
        "key": "4242:12",
        "kind": "job",
        "name": "comparison_cache.manifest",
        "start_ms": 68531.0,
        "dur_ms": null,
        "outcome": null,
        "state": "unfinished",
        "client": null,
        "pid": 4242,
        "span": 12,
        "parent": "4242:11",
        "attrs": {
          "key": "store 4922384 519dabc merge_base"
        },
        "elapsed_ms": 30003.0,
        "opens": 3,
        "path": [
          {
            "key": "4242:11",
            "kind": "request",
            "name": "GET /api/plugin/github/pull-comparison"
          }
        ]
      }
    ]
  },
  "not_failures": {}
}
? 0
```

## Test: a person with no log yet is told where one is written

```console
$ METABROWSER_STATE_DIR=$PWD/empty metab --event-log --api /api/tree
Error: there is no event log at [CWD]/empty/events: a served metab writes one there (METABROWSER_EVENT_LOG=0 turns it off, and a one-shot command writes none)
? 1
```

## Test: the flag names the folder, so ROOT is refused

```console
$ METABROWSER_STATE_DIR=$PWD/state metab . --event-log --api /api/tree
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --event-log names the folder to open; ROOT is not used with it               │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: a mode with no folder refuses it

```console
$ METABROWSER_STATE_DIR=$PWD/state metab --event-log --doctor
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --event-log not valid with --doctor                                          │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```
