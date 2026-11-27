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
  "$TRYSCRIPT_TEST_DIR/../fixtures/github-gh-requests/events-20261126T100000Z-p4242-000.jsonl"
  "$TRYSCRIPT_TEST_DIR/../fixtures/github-gh-requests/events-20261126T100020Z-p4343-000.jsonl"
  state/events/ &&
  touch -t 202611261001.00
  state/events/events-20261126T100000Z-p4242-000.jsonl
  state/events/events-20261126T100020Z-p4343-000.jsonl
---
# Golden tests: what the servers asked of GitHub, through `--api`

`/api/plugin/github/gh-requests` reads the `gh` spans of the structured event log over a
window and says what they add up to: the calls, by the lane each served, the budget each
was charged to, and the job each ran in, what GitHub charged for them, the share it
answered `304`, how long gh took, how long each waited for a network slot, how many ran
at once, whether a less urgent lane’s call started ahead of a more urgent one asked
before it, and which reads repeated.
The GitHub plugin’s `gh_requests.py` names every field.

The fixture is one minute of a synthetic server, process 4242: the source’s refresh
reads #7, the pull request the server attends, and checks the account twice a moment
apart, the page’s probe of the pull request’s issue every five seconds is answered
`304`, the Pulls tab reads the catalog (a backfill page waiting for a network slot) and
the open pull requests’ statuses, the prefetch reads #9 with an account check of its
own, two asks read one batch of the cores walk at once, a files list waits for a slot
and its read never answers, the reader clicks Refresh, the GitHub status check runs
`gh --version` and `gh auth status`, a size read asks for no status, and one call was
recorded before calls recorded their lane, budget, and status.
One call ends after the window closes.
A second server, process 4343, reads one pull request of another repository.
The segments were written by the production `gh.loggable_args` and `gh.fingerprint`.

## Test: one server’s calls in a window

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/plugin/github/gh-requests?since=2026-11-26T10:00:00Z&until=2026-11-26T10:01:00Z&pid=4242&buckets=6'
api: /api/plugin/github/gh-requests?since=2026-11-26T10:00:00Z&until=2026-11-26T10:01:00Z&pid=4242&buckets=6
status: 200
{
  "schema_version": 1,
  "directory": "[CWD]/state/events",
  "state": "present",
  "query": {
    "since": "2026-11-26T10:00:00Z",
    "until": "2026-11-26T10:01:00Z",
    "pid": 4242,
    "buckets": 6
  },
  "files": [
    "events-20261126T100020Z-p4343-000.jsonl",
    "events-20261126T100000Z-p4242-000.jsonl"
  ],
  "scanned": 56,
  "pids": [
    4242
  ],
  "duplicate_window_s": 4.0,
  "requests": {
    "requests": 19,
    "commands": {
      "rest": 11,
      "graphql": 6,
      "other": 2
    },
    "statuses": {
      "200": 8,
      "304": 6
    },
    "no_status": {
      "failed": 1,
      "unread": 1,
      "unrecorded": 1
    },
    "core": 2,
    "graphql_points": 7,
    "share_304": 0.75,
    "conditional": 7,
    "cache_hits": 6,
    "latency": {
      "p50_ms": 500.0,
      "p95_ms": 30006.0,
      "max_ms": 30006.0,
      "total_ms": 40201.0
    },
    "duplicates": {
      "in_flight": 1,
      "repeated": 2
    },
    "peak_in_flight": 3,
    "queued": {
      "waits": 3,
      "p50_ms": 810.4,
      "p95_ms": 1503.1,
      "max_ms": 1503.1,
      "total_ms": 2313.7
    }
  },
  "lanes": {
    "visible": {
      "requests": 8,
      "commands": {
        "rest": 5,
        "graphql": 1,
        "other": 2
      },
      "statuses": {
        "200": 1,
        "304": 3
      },
      "no_status": {
        "failed": 1,
        "unread": 1,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 1,
      "share_304": 1.0,
      "conditional": 3,
      "cache_hits": 3,
      "latency": {
        "p50_ms": 400.0,
        "p95_ms": 30006.0,
        "max_ms": 30006.0,
        "total_ms": 32881.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 2,
      "queued": {
        "waits": 1,
        "p50_ms": 1503.1,
        "p95_ms": 1503.1,
        "max_ms": 1503.1,
        "total_ms": 1503.1
      }
    },
    "attended": {
      "requests": 4,
      "commands": {
        "rest": 3,
        "graphql": 1,
        "other": 0
      },
      "statuses": {
        "200": 2,
        "304": 2
      },
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 1,
      "graphql_points": 1,
      "share_304": 0.667,
      "conditional": 3,
      "cache_hits": 2,
      "latency": {
        "p50_ms": 380.0,
        "p95_ms": 840.0,
        "max_ms": 840.0,
        "total_ms": 2180.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 1
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    "prefetch": {
      "requests": 2,
      "commands": {
        "rest": 2,
        "graphql": 0,
        "other": 0
      },
      "statuses": {
        "200": 1,
        "304": 1
      },
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 1,
      "graphql_points": 0,
      "share_304": 0.5,
      "conditional": 1,
      "cache_hits": 1,
      "latency": {
        "p50_ms": 360.0,
        "p95_ms": 640.0,
        "max_ms": 640.0,
        "total_ms": 1000.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 1
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    "background": {
      "requests": 4,
      "commands": {
        "rest": 0,
        "graphql": 4,
        "other": 0
      },
      "statuses": {
        "200": 4
      },
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 5,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 700.0,
        "p95_ms": 1240.0,
        "max_ms": 1240.0,
        "total_ms": 3640.0
      },
      "duplicates": {
        "in_flight": 1,
        "repeated": 0
      },
      "peak_in_flight": 2,
      "queued": {
        "waits": 2,
        "p50_ms": 0.2,
        "p95_ms": 810.4,
        "max_ms": 810.4,
        "total_ms": 810.6
      }
    },
    "unknown": {
      "requests": 1,
      "commands": {
        "rest": 1,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 1
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 500.0,
        "p95_ms": 500.0,
        "max_ms": 500.0,
        "total_ms": 500.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    }
  },
  "budgets": {
    "reader": {
      "requests": 1,
      "commands": {
        "rest": 1,
        "graphql": 0,
        "other": 0
      },
      "statuses": {
        "304": 1
      },
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": 1.0,
      "conditional": 1,
      "cache_hits": 1,
      "latency": {
        "p50_ms": 400.0,
        "p95_ms": 400.0,
        "max_ms": 400.0,
        "total_ms": 400.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    "automatic": {
      "requests": 12,
      "commands": {
        "rest": 7,
        "graphql": 3,
        "other": 2
      },
      "statuses": {
        "200": 4,
        "304": 4
      },
      "no_status": {
        "failed": 1,
        "unread": 1,
        "unrecorded": 0
      },
      "core": 1,
      "graphql_points": 4,
      "share_304": 0.8,
      "conditional": 5,
      "cache_hits": 4,
      "latency": {
        "p50_ms": 420.0,
        "p95_ms": 30006.0,
        "max_ms": 30006.0,
        "total_ms": 35901.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 1
      },
      "peak_in_flight": 3,
      "queued": {
        "waits": 2,
        "p50_ms": 0.2,
        "p95_ms": 1503.1,
        "max_ms": 1503.1,
        "total_ms": 1503.3
      }
    },
    "speculative": {
      "requests": 3,
      "commands": {
        "rest": 2,
        "graphql": 1,
        "other": 0
      },
      "statuses": {
        "200": 2,
        "304": 1
      },
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 1,
      "graphql_points": 1,
      "share_304": 0.5,
      "conditional": 1,
      "cache_hits": 1,
      "latency": {
        "p50_ms": 640.0,
        "p95_ms": 1010.0,
        "max_ms": 1010.0,
        "total_ms": 2010.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 1
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 1,
        "p50_ms": 810.4,
        "p95_ms": 810.4,
        "max_ms": 810.4,
        "total_ms": 810.4
      }
    },
    "walk": {
      "requests": 2,
      "commands": {
        "rest": 0,
        "graphql": 2,
        "other": 0
      },
      "statuses": {
        "200": 2
      },
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 2,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 690.0,
        "p95_ms": 700.0,
        "max_ms": 700.0,
        "total_ms": 1390.0
      },
      "duplicates": {
        "in_flight": 1,
        "repeated": 0
      },
      "peak_in_flight": 2,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    "unknown": {
      "requests": 1,
      "commands": {
        "rest": 1,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 1
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 500.0,
        "p95_ms": 500.0,
        "max_ms": 500.0,
        "total_ms": 500.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    }
  },
  "jobs": [
    {
      "job": "checkout._pull_job",
      "kind": "job",
      "requests": 7,
      "commands": {
        "rest": 6,
        "graphql": 1,
        "other": 0
      },
      "statuses": {
        "200": 3,
        "304": 4
      },
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 2,
      "graphql_points": 1,
      "share_304": 0.667,
      "conditional": 5,
      "cache_hits": 4,
      "latency": {
        "p50_ms": 400.0,
        "p95_ms": 840.0,
        "max_ms": 840.0,
        "total_ms": 3580.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 2
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    {
      "job": "pull_cores._prepare",
      "kind": "job",
      "requests": 2,
      "commands": {
        "rest": 0,
        "graphql": 2,
        "other": 0
      },
      "statuses": {
        "200": 2
      },
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 2,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 690.0,
        "p95_ms": 700.0,
        "max_ms": 700.0,
        "total_ms": 1390.0
      },
      "duplicates": {
        "in_flight": 1,
        "repeated": 0
      },
      "peak_in_flight": 2,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    {
      "job": "pull_list_route._run_refresh",
      "kind": "job",
      "requests": 2,
      "commands": {
        "rest": 0,
        "graphql": 2,
        "other": 0
      },
      "statuses": {
        "200": 2
      },
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 2,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 920.0,
        "p95_ms": 1010.0,
        "max_ms": 1010.0,
        "total_ms": 1930.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 1,
        "p50_ms": 810.4,
        "p95_ms": 810.4,
        "max_ms": 810.4,
        "total_ms": 810.4
      }
    },
    {
      "job": "served_pull.ServedPull._probe",
      "kind": "job",
      "requests": 2,
      "commands": {
        "rest": 2,
        "graphql": 0,
        "other": 0
      },
      "statuses": {
        "304": 2
      },
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": 1.0,
      "conditional": 2,
      "cache_hits": 2,
      "latency": {
        "p50_ms": 290.0,
        "p95_ms": 300.0,
        "max_ms": 300.0,
        "total_ms": 590.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    {
      "job": "POST /api/plugin/github/status",
      "kind": "request",
      "requests": 2,
      "commands": {
        "rest": 0,
        "graphql": 0,
        "other": 2
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 45.0,
        "p95_ms": 420.0,
        "max_ms": 420.0,
        "total_ms": 465.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    {
      "job": "pull_files_refresh.refresh_files",
      "kind": "job",
      "requests": 1,
      "commands": {
        "rest": 1,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 1,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 30006.0,
        "p95_ms": 30006.0,
        "max_ms": 30006.0,
        "total_ms": 30006.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 1,
        "p50_ms": 1503.1,
        "p95_ms": 1503.1,
        "max_ms": 1503.1,
        "total_ms": 1503.1
      }
    },
    {
      "job": "pull_status_scan._scan_job",
      "kind": "job",
      "requests": 1,
      "commands": {
        "rest": 0,
        "graphql": 1,
        "other": 0
      },
      "statuses": {
        "200": 1
      },
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 2,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 1240.0,
        "p95_ms": 1240.0,
        "max_ms": 1240.0,
        "total_ms": 1240.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 1,
        "p50_ms": 0.2,
        "p95_ms": 0.2,
        "max_ms": 0.2,
        "total_ms": 0.2
      }
    },
    {
      "job": null,
      "kind": "none",
      "requests": 1,
      "commands": {
        "rest": 1,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 1,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 500.0,
        "p95_ms": 500.0,
        "max_ms": 500.0,
        "total_ms": 500.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    {
      "job": null,
      "kind": "unknown",
      "requests": 1,
      "commands": {
        "rest": 1,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 1
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 500.0,
        "p95_ms": 500.0,
        "max_ms": 500.0,
        "total_ms": 500.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    }
  ],
  "jobs_more": 0,
  "in_flight": {
    "peak": 3,
    "peak_at": "2026-11-26T10:00:01.506Z",
    "first": "2026-11-26T10:00:01.010Z",
    "last": "2026-11-26T10:00:43.511Z",
    "levels_ms": {
      "0": 6923.0,
      "1": 31863.0,
      "2": 2807.0,
      "3": 908.0
    },
    "bucket_ms": 7083.5,
    "spans_peak": 3,
    "slotted_peak": 2,
    "series": [
      {
        "at_ms": 0.0,
        "peak": 3,
        "mean": 1.13
      },
      {
        "at_ms": 7083.5,
        "peak": 1,
        "mean": 0.28
      },
      {
        "at_ms": 14167.0,
        "peak": 2,
        "mean": 1.06
      },
      {
        "at_ms": 21250.5,
        "peak": 2,
        "mean": 1.07
      },
      {
        "at_ms": 28334.0,
        "peak": 2,
        "mean": 1.14
      },
      {
        "at_ms": 35417.5,
        "peak": 1,
        "mean": 1.0
      }
    ]
  },
  "order": {
    "visible": {
      "attended": {
        "overtook": 0,
        "beside": 1
      },
      "prefetch": {
        "overtook": 0,
        "beside": 0
      },
      "background": {
        "overtook": 0,
        "beside": 1
      }
    },
    "attended": {
      "prefetch": {
        "overtook": 0,
        "beside": 0
      },
      "background": {
        "overtook": 0,
        "beside": 1
      }
    },
    "prefetch": {
      "background": {
        "overtook": 0,
        "beside": 0
      }
    }
  },
  "repeats": [
    {
      "asks": "gh api user",
      "fingerprint": "eb500829d7df0806",
      "in_flight": 0,
      "repeated": 2
    },
    {
      "asks": "gh api graphql",
      "fingerprint": "c38e2696fb73af9a",
      "in_flight": 1,
      "repeated": 0
    }
  ],
  "unrecorded": {
    "first_answer_seen": "when a page first showed GitHub's answer: a page reports a wait only once it is late, so the time to a first answer is not in the log",
    "local_cache_hits": "reads the server answered from its own store: those make no gh call, so cache_hits counts only the 304s GitHub answered",
    "store_turn_waits": "time a job waited for its turn at the store: queued counts only the waits for a network slot"
  }
}
? 0
```

## Test: every server’s calls, the second server’s among those of no span

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/plugin/github/gh-requests?since=2026-11-26T10:00:30Z&until=2026-11-26T10:01:00Z&buckets=2'
api: /api/plugin/github/gh-requests?since=2026-11-26T10:00:30Z&until=2026-11-26T10:01:00Z&buckets=2
status: 200
{
  "schema_version": 1,
  "directory": "[CWD]/state/events",
  "state": "present",
  "query": {
    "since": "2026-11-26T10:00:30Z",
    "until": "2026-11-26T10:01:00Z",
    "pid": null,
    "buckets": 2
  },
  "files": [
    "events-20261126T100020Z-p4343-000.jsonl",
    "events-20261126T100000Z-p4242-000.jsonl"
  ],
  "scanned": 56,
  "pids": [
    4242,
    4343
  ],
  "duplicate_window_s": 4.0,
  "requests": {
    "requests": 4,
    "commands": {
      "rest": 4,
      "graphql": 0,
      "other": 0
    },
    "statuses": {
      "200": 1
    },
    "no_status": {
      "failed": 1,
      "unread": 1,
      "unrecorded": 1
    },
    "core": 1,
    "graphql_points": 0,
    "share_304": 0.0,
    "conditional": 1,
    "cache_hits": 0,
    "latency": {
      "p50_ms": 500.0,
      "p95_ms": 30006.0,
      "max_ms": 30006.0,
      "total_ms": 31506.0
    },
    "duplicates": {
      "in_flight": 0,
      "repeated": 0
    },
    "peak_in_flight": 2,
    "queued": {
      "waits": 1,
      "p50_ms": 1503.1,
      "p95_ms": 1503.1,
      "max_ms": 1503.1,
      "total_ms": 1503.1
    }
  },
  "lanes": {
    "visible": {
      "requests": 3,
      "commands": {
        "rest": 3,
        "graphql": 0,
        "other": 0
      },
      "statuses": {
        "200": 1
      },
      "no_status": {
        "failed": 1,
        "unread": 1,
        "unrecorded": 0
      },
      "core": 1,
      "graphql_points": 0,
      "share_304": 0.0,
      "conditional": 1,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 500.0,
        "p95_ms": 30006.0,
        "max_ms": 30006.0,
        "total_ms": 31006.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 2,
      "queued": {
        "waits": 1,
        "p50_ms": 1503.1,
        "p95_ms": 1503.1,
        "max_ms": 1503.1,
        "total_ms": 1503.1
      }
    },
    "attended": {
      "requests": 0,
      "commands": {
        "rest": 0,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 0,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    "prefetch": {
      "requests": 0,
      "commands": {
        "rest": 0,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 0,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    "background": {
      "requests": 0,
      "commands": {
        "rest": 0,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 0,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    "unknown": {
      "requests": 1,
      "commands": {
        "rest": 1,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 1
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 500.0,
        "p95_ms": 500.0,
        "max_ms": 500.0,
        "total_ms": 500.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    }
  },
  "budgets": {
    "reader": {
      "requests": 0,
      "commands": {
        "rest": 0,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 0,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    "automatic": {
      "requests": 3,
      "commands": {
        "rest": 3,
        "graphql": 0,
        "other": 0
      },
      "statuses": {
        "200": 1
      },
      "no_status": {
        "failed": 1,
        "unread": 1,
        "unrecorded": 0
      },
      "core": 1,
      "graphql_points": 0,
      "share_304": 0.0,
      "conditional": 1,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 500.0,
        "p95_ms": 30006.0,
        "max_ms": 30006.0,
        "total_ms": 31006.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 2,
      "queued": {
        "waits": 1,
        "p50_ms": 1503.1,
        "p95_ms": 1503.1,
        "max_ms": 1503.1,
        "total_ms": 1503.1
      }
    },
    "speculative": {
      "requests": 0,
      "commands": {
        "rest": 0,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 0,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    "walk": {
      "requests": 0,
      "commands": {
        "rest": 0,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 0,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    "unknown": {
      "requests": 1,
      "commands": {
        "rest": 1,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 1
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 500.0,
        "p95_ms": 500.0,
        "max_ms": 500.0,
        "total_ms": 500.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    }
  },
  "jobs": [
    {
      "job": null,
      "kind": "none",
      "requests": 2,
      "commands": {
        "rest": 2,
        "graphql": 0,
        "other": 0
      },
      "statuses": {
        "200": 1
      },
      "no_status": {
        "failed": 0,
        "unread": 1,
        "unrecorded": 0
      },
      "core": 1,
      "graphql_points": 0,
      "share_304": 0.0,
      "conditional": 1,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 500.0,
        "p95_ms": 500.0,
        "max_ms": 500.0,
        "total_ms": 1000.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    },
    {
      "job": "pull_files_refresh.refresh_files",
      "kind": "job",
      "requests": 1,
      "commands": {
        "rest": 1,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 1,
        "unread": 0,
        "unrecorded": 0
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 30006.0,
        "p95_ms": 30006.0,
        "max_ms": 30006.0,
        "total_ms": 30006.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 1,
        "p50_ms": 1503.1,
        "p95_ms": 1503.1,
        "max_ms": 1503.1,
        "total_ms": 1503.1
      }
    },
    {
      "job": null,
      "kind": "unknown",
      "requests": 1,
      "commands": {
        "rest": 1,
        "graphql": 0,
        "other": 0
      },
      "statuses": {},
      "no_status": {
        "failed": 0,
        "unread": 0,
        "unrecorded": 1
      },
      "core": 0,
      "graphql_points": 0,
      "share_304": null,
      "conditional": 0,
      "cache_hits": 0,
      "latency": {
        "p50_ms": 500.0,
        "p95_ms": 500.0,
        "max_ms": 500.0,
        "total_ms": 500.0
      },
      "duplicates": {
        "in_flight": 0,
        "repeated": 0
      },
      "peak_in_flight": 1,
      "queued": {
        "waits": 0,
        "p50_ms": null,
        "p95_ms": null,
        "max_ms": null,
        "total_ms": 0
      }
    }
  ],
  "jobs_more": 0,
  "in_flight": {
    "peak": 2,
    "peak_at": "2026-11-26T10:00:30.000Z",
    "first": "2026-11-26T10:00:13.505Z",
    "last": "2026-11-26T10:00:43.511Z",
    "levels_ms": {
      "1": 28506.0,
      "2": 1500.0
    },
    "bucket_ms": 15003.0,
    "spans_peak": 2,
    "slotted_peak": 1,
    "series": [
      {
        "at_ms": 0.0,
        "peak": 1,
        "mean": 1.0
      },
      {
        "at_ms": 15003.0,
        "peak": 2,
        "mean": 1.1
      }
    ]
  },
  "order": {
    "visible": {
      "attended": {
        "overtook": 0,
        "beside": 0
      },
      "prefetch": {
        "overtook": 0,
        "beside": 0
      },
      "background": {
        "overtook": 0,
        "beside": 0
      }
    },
    "attended": {
      "prefetch": {
        "overtook": 0,
        "beside": 0
      },
      "background": {
        "overtook": 0,
        "beside": 0
      }
    },
    "prefetch": {
      "background": {
        "overtook": 0,
        "beside": 0
      }
    }
  },
  "repeats": [],
  "unrecorded": {
    "first_answer_seen": "when a page first showed GitHub's answer: a page reports a wait only once it is late, so the time to a first answer is not in the log",
    "local_cache_hits": "reads the server answered from its own store: those make no gh call, so cache_hits counts only the 304s GitHub answered",
    "store_turn_waits": "time a job waited for its turn at the store: queued counts only the waits for a network slot"
  }
}
? 0
```

## Test: a parameter the report cannot take is refused

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/plugin/github/gh-requests?buckets=0'
api: /api/plugin/github/gh-requests?buckets=0
status: 400
{
  "error": "buckets must be from 1 to 600",
  "code": "invalid_query"
}
Error: /api/plugin/github/gh-requests?buckets=0 returned HTTP 400
? 1
```

## Test: a window that closes before it opens is refused

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/plugin/github/gh-requests?since=2026-11-26T10:01:00Z&until=2026-11-26T10:00:00Z'
api: /api/plugin/github/gh-requests?since=2026-11-26T10:01:00Z&until=2026-11-26T10:00:00Z
status: 400
{
  "error": "until must not be before since",
  "code": "invalid_query"
}
Error: /api/plugin/github/gh-requests?since=2026-11-26T10:01:00Z&until=2026-11-26T10:00:00Z returned HTTP 400
? 1
```
