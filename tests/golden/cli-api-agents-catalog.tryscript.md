---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
before: >-
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../agents_synthetic_home.py" root
  > fixture.log 2>&1 &&
  mkdir root/plain &&
  printf 'not a directory\n' > cache-is-a-file
---
# Golden tests: the agents catalog and its routes through `--api`

The `agents` plugin keeps a catalog of every Claude Code and Codex session under the
served root and answers five routes from it: `catalog`, `sessions`, `session`,
`records`, and `live`. `tests/agents_synthetic_home.py` writes the homes served here,
`.claude` and `.codex` under `root`, from constants, so every id, time, and count is
asserted literally.

A request normally answers from what the background worker has summarized so far.
These commands pass `sync=1`, which waits until the catalog is fully summarized, and
`now=1800000000`, which fixes the clock the passes and the liveness checks read.
Each command names its cache directory with `METABROWSER_CACHE_DIR`, since each runs a
fresh server process: the first fills the cache and the later ones load from it.
No response names an absolute path.

## Test: the catalog of a root that holds both homes

The first run reads every session, so `progress` shows `read: 13` and `from_cache: 0`.
The synthetic Claude Code pid file names a process that does not exist, so no Claude
Code session is running; two Codex threads are, one by a recent update and one by an
active turn.

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/catalog?sync=1&now=1800000000'
api: /api/plugin/agents/catalog?sync=1&now=1800000000
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "homes": [
    {
      "agent": "claude",
      "path": ".claude",
      "state": "idle",
      "sessions": 5,
      "summarized": 5,
      "running": 0,
      "size_bytes": 4620,
      "oldest_activity": 1799913610.0,
      "newest_activity": 1799917201.0,
      "discover_limit_reached": false
    },
    {
      "agent": "codex",
      "path": ".codex",
      "state": "idle",
      "sessions": 8,
      "summarized": 8,
      "running": 2,
      "size_bytes": 3022,
      "oldest_activity": 1799910000.0,
      "newest_activity": 1799999970.0,
      "discover_limit_reached": false
    }
  ],
  "totals": {
    "sessions": 13,
    "summarized": 13,
    "running": 2,
    "size_bytes": 7642,
    "by_agent": {
      "claude": 5,
      "codex": 8
    },
    "by_origin": {
      "human": 8,
      "scheduled": 1,
      "subagent": 3,
      "review": 1
    }
  },
  "size_histogram": {
    "unit": "bytes",
    "buckets": [
      {
        "lower": 0,
        "upper": 1024,
        "count": 11
      },
      {
        "lower": 1024,
        "upper": 4096,
        "count": 2
      },
      {
        "lower": 4096,
        "upper": 16384,
        "count": 0
      },
      {
        "lower": 16384,
        "upper": 65536,
        "count": 0
      },
      {
        "lower": 65536,
        "upper": 262144,
        "count": 0
      },
      {
        "lower": 262144,
        "upper": 1048576,
        "count": 0
      },
      {
        "lower": 1048576,
        "upper": 4194304,
        "count": 0
      },
      {
        "lower": 4194304,
        "upper": 16777216,
        "count": 0
      },
      {
        "lower": 16777216,
        "upper": 67108864,
        "count": 0
      },
      {
        "lower": 67108864,
        "upper": 268435456,
        "count": 0
      },
      {
        "lower": 268435456,
        "upper": 1073741824,
        "count": 0
      },
      {
        "lower": 1073741824,
        "upper": 4294967296,
        "count": 0
      },
      {
        "lower": 4294967296,
        "upper": null,
        "count": 0
      }
    ]
  },
  "per_day": [
    {
      "day": "2027-01-14",
      "sessions": 6
    },
    {
      "day": "2027-01-15",
      "sessions": 7
    }
  ],
  "progress": {
    "state": "idle",
    "total": 13,
    "summarized": 13,
    "from_cache": 0,
    "read": 13,
    "failed": 0,
    "complete": true
  },
  "freshness": {
    "fast_pass_at": 1800000000.0,
    "summary_pass_at": 1800000000.0,
    "passes": 2
  },
  "cache": {
    "state": "ok",
    "write_errors": 0
  },
  "drift": {
    "clean": false,
    "unknown_types": {
      "<invalid-json>": 1,
      "assistant/hologram": 1,
      "event_msg/novel_event": 1,
      "never-seen-type": 1,
      "novel_record": 1,
      "thread_item/holographicThing": 1
    },
    "unexpected_columns": {
      "history.thread_items.zz_new_col": 8,
      "state.threads.zz_future": 9
    },
    "missing_columns": {},
    "read_errors": {},
    "truncated": false
  },
  "engines": {
    "session": "builtin",
    "drift": "builtin"
  }
}
? 0
```

## Test: a second server loads the summaries from the cache

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/sessions?sync=1&now=1800000000&limit=1'
api: /api/plugin/agents/sessions?sync=1&now=1800000000&limit=1
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "filters": {
    "agent": null,
    "origin": [],
    "status": [],
    "project": null,
    "model": null,
    "since": null,
    "until": null
  },
  "sort": "activity",
  "order": "desc",
  "offset": 0,
  "limit": 1,
  "next_offset": 1,
  "total": 13,
  "available": 13,
  "totals": {
    "size_bytes": 7642,
    "running": 2
  },
  "facets": {
    "agent": {
      "claude": 5,
      "codex": 8
    },
    "origin": {
      "human": 8,
      "scheduled": 1,
      "subagent": 3,
      "review": 1
    },
    "status": {
      "running": 2,
      "finished": 4,
      "failed": 2,
      "unknown": 5
    },
    "project": [
      [
        "/work/gamma",
        8
      ],
      [
        "/work/alpha",
        1
      ],
      [
        "/work/beta",
        1
      ]
    ]
  },
  "progress": {
    "state": "idle",
    "total": 13,
    "summarized": 13,
    "from_cache": 13,
    "read": 0,
    "failed": 0,
    "complete": true
  },
  "freshness": {
    "fast_pass_at": 1800000000.0,
    "summary_pass_at": 1800000000.0,
    "passes": 2
  },
  "cache": {
    "state": "ok",
    "write_errors": 0
  },
  "sessions": [
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000005",
      "home": ".codex",
      "title": "title 5",
      "parent_id": null,
      "child_ids": [],
      "origin": "human",
      "project": "/work/gamma",
      "git_branch": "main",
      "started_at": 1799999370.0,
      "ended_at": null,
      "last_activity": 1799999970.0,
      "duration_seconds": null,
      "size_bytes": 0,
      "records": 0,
      "replayed_records": 0,
      "turns": 0,
      "models": [
        "gpt-test-1"
      ],
      "status": "running",
      "summarized": true,
      "source_paths": []
    }
  ]
}
? 0
```

## Test: the catalog of one home folder

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/catalog?sync=1&now=1800000000&folder=.codex'
api: /api/plugin/agents/catalog?sync=1&now=1800000000&folder=.codex
status: 200
{
  "folder": ".codex",
  "now": 1800000000.0,
  "homes": [
    {
      "agent": "codex",
      "path": ".codex",
      "state": "idle",
      "sessions": 8,
      "summarized": 8,
      "running": 2,
      "size_bytes": 3022,
      "oldest_activity": 1799910000.0,
      "newest_activity": 1799999970.0,
      "discover_limit_reached": false
    }
  ],
  "totals": {
    "sessions": 8,
    "summarized": 8,
    "running": 2,
    "size_bytes": 3022,
    "by_agent": {
      "codex": 8
    },
    "by_origin": {
      "human": 6,
      "subagent": 1,
      "review": 1
    }
  },
  "size_histogram": {
    "unit": "bytes",
    "buckets": [
      {
        "lower": 0,
        "upper": 1024,
        "count": 7
      },
      {
        "lower": 1024,
        "upper": 4096,
        "count": 1
      },
      {
        "lower": 4096,
        "upper": 16384,
        "count": 0
      },
      {
        "lower": 16384,
        "upper": 65536,
        "count": 0
      },
      {
        "lower": 65536,
        "upper": 262144,
        "count": 0
      },
      {
        "lower": 262144,
        "upper": 1048576,
        "count": 0
      },
      {
        "lower": 1048576,
        "upper": 4194304,
        "count": 0
      },
      {
        "lower": 4194304,
        "upper": 16777216,
        "count": 0
      },
      {
        "lower": 16777216,
        "upper": 67108864,
        "count": 0
      },
      {
        "lower": 67108864,
        "upper": 268435456,
        "count": 0
      },
      {
        "lower": 268435456,
        "upper": 1073741824,
        "count": 0
      },
      {
        "lower": 1073741824,
        "upper": 4294967296,
        "count": 0
      },
      {
        "lower": 4294967296,
        "upper": null,
        "count": 0
      }
    ]
  },
  "per_day": [
    {
      "day": "2027-01-14",
      "sessions": 1
    },
    {
      "day": "2027-01-15",
      "sessions": 7
    }
  ],
  "progress": {
    "state": "idle",
    "total": 8,
    "summarized": 8,
    "from_cache": 8,
    "read": 0,
    "failed": 0,
    "complete": true
  },
  "freshness": {
    "fast_pass_at": 1800000000.0,
    "summary_pass_at": 1800000000.0,
    "passes": 1
  },
  "cache": {
    "state": "ok",
    "write_errors": 0
  },
  "drift": {
    "clean": false,
    "unknown_types": {
      "<invalid-json>": 1,
      "event_msg/novel_event": 1,
      "novel_record": 1,
      "thread_item/holographicThing": 1
    },
    "unexpected_columns": {
      "history.thread_items.zz_new_col": 8,
      "state.threads.zz_future": 9
    },
    "missing_columns": {},
    "read_errors": {},
    "truncated": false
  },
  "engines": {
    "session": "builtin",
    "drift": "builtin"
  }
}
? 0
```

## Test: sessions filtered by agent and origin

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/sessions?sync=1&now=1800000000&agent=claude&origin=subagent&sort=size'
api: /api/plugin/agents/sessions?sync=1&now=1800000000&agent=claude&origin=subagent&sort=size
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "filters": {
    "agent": "claude",
    "origin": [
      "subagent"
    ],
    "status": [],
    "project": null,
    "model": null,
    "since": null,
    "until": null
  },
  "sort": "size",
  "order": "desc",
  "offset": 0,
  "limit": 100,
  "next_offset": null,
  "total": 2,
  "available": 13,
  "totals": {
    "size_bytes": 703,
    "running": 0
  },
  "facets": {
    "agent": {
      "claude": 5,
      "codex": 8
    },
    "origin": {
      "human": 8,
      "scheduled": 1,
      "subagent": 3,
      "review": 1
    },
    "status": {
      "running": 2,
      "finished": 4,
      "failed": 2,
      "unknown": 5
    },
    "project": [
      [
        "/work/gamma",
        8
      ],
      [
        "/work/alpha",
        1
      ],
      [
        "/work/beta",
        1
      ]
    ]
  },
  "progress": {
    "state": "idle",
    "total": 13,
    "summarized": 13,
    "from_cache": 13,
    "read": 0,
    "failed": 0,
    "complete": true
  },
  "freshness": {
    "fast_pass_at": 1800000000.0,
    "summary_pass_at": 1800000000.0,
    "passes": 2
  },
  "cache": {
    "state": "ok",
    "write_errors": 0
  },
  "sessions": [
    {
      "agent": "claude",
      "session_id": "agent-aaa",
      "home": ".claude",
      "title": "Explore code",
      "parent_id": "11111111-1111-4111-8111-111111111111",
      "child_ids": [
        "agent-bbb"
      ],
      "origin": "subagent",
      "project": null,
      "git_branch": null,
      "started_at": 1799913621.0,
      "ended_at": 1799913625.0,
      "last_activity": 1799913626.0,
      "duration_seconds": 4.0,
      "size_bytes": 467,
      "records": 2,
      "replayed_records": 0,
      "turns": 1,
      "models": [
        "claude-sub-1"
      ],
      "status": "finished",
      "summarized": true,
      "source_paths": [
        ".claude/projects/-work-alpha/11111111-1111-4111-8111-111111111111/subagents/agent-aaa.jsonl"
      ]
    },
    {
      "agent": "claude",
      "session_id": "agent-bbb",
      "home": ".claude",
      "title": "Nested",
      "parent_id": "agent-aaa",
      "child_ids": [],
      "origin": "subagent",
      "project": null,
      "git_branch": null,
      "started_at": 1799913626.0,
      "ended_at": 1799913626.0,
      "last_activity": 1799913627.0,
      "duration_seconds": 0.0,
      "size_bytes": 236,
      "records": 1,
      "replayed_records": 0,
      "turns": 0,
      "models": [
        "claude-sub-2"
      ],
      "status": "finished",
      "summarized": true,
      "source_paths": [
        ".claude/projects/-work-alpha/11111111-1111-4111-8111-111111111111/subagents/agent-bbb.jsonl"
      ]
    }
  ]
}
? 0
```

## Test: running sessions

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/sessions?sync=1&now=1800000000&status=running&sort=title'
api: /api/plugin/agents/sessions?sync=1&now=1800000000&status=running&sort=title
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "filters": {
    "agent": null,
    "origin": [],
    "status": [
      "running"
    ],
    "project": null,
    "model": null,
    "since": null,
    "until": null
  },
  "sort": "title",
  "order": "asc",
  "offset": 0,
  "limit": 100,
  "next_offset": null,
  "total": 2,
  "available": 13,
  "totals": {
    "size_bytes": 0,
    "running": 2
  },
  "facets": {
    "agent": {
      "claude": 5,
      "codex": 8
    },
    "origin": {
      "human": 8,
      "scheduled": 1,
      "subagent": 3,
      "review": 1
    },
    "status": {
      "running": 2,
      "finished": 4,
      "failed": 2,
      "unknown": 5
    },
    "project": [
      [
        "/work/gamma",
        8
      ],
      [
        "/work/alpha",
        1
      ],
      [
        "/work/beta",
        1
      ]
    ]
  },
  "progress": {
    "state": "idle",
    "total": 13,
    "summarized": 13,
    "from_cache": 13,
    "read": 0,
    "failed": 0,
    "complete": true
  },
  "freshness": {
    "fast_pass_at": 1800000000.0,
    "summary_pass_at": 1800000000.0,
    "passes": 2
  },
  "cache": {
    "state": "ok",
    "write_errors": 0
  },
  "sessions": [
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000005",
      "home": ".codex",
      "title": "title 5",
      "parent_id": null,
      "child_ids": [],
      "origin": "human",
      "project": "/work/gamma",
      "git_branch": "main",
      "started_at": 1799999370.0,
      "ended_at": null,
      "last_activity": 1799999970.0,
      "duration_seconds": null,
      "size_bytes": 0,
      "records": 0,
      "replayed_records": 0,
      "turns": 0,
      "models": [
        "gpt-test-1"
      ],
      "status": "running",
      "summarized": true,
      "source_paths": []
    },
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000006",
      "home": ".codex",
      "title": "title 6",
      "parent_id": null,
      "child_ids": [],
      "origin": "human",
      "project": "/work/gamma",
      "git_branch": "main",
      "started_at": 1799998800.0,
      "ended_at": null,
      "last_activity": 1799999400.0,
      "duration_seconds": null,
      "size_bytes": 0,
      "records": 0,
      "replayed_records": 0,
      "turns": 0,
      "models": [
        "gpt-test-1"
      ],
      "status": "running",
      "summarized": true,
      "source_paths": []
    }
  ]
}
? 0
```

## Test: a page of sessions by size, then the next

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/sessions?sync=1&now=1800000000&sort=size&limit=2'
api: /api/plugin/agents/sessions?sync=1&now=1800000000&sort=size&limit=2
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "filters": {
    "agent": null,
    "origin": [],
    "status": [],
    "project": null,
    "model": null,
    "since": null,
    "until": null
  },
  "sort": "size",
  "order": "desc",
  "offset": 0,
  "limit": 2,
  "next_offset": 2,
  "total": 13,
  "available": 13,
  "totals": {
    "size_bytes": 7642,
    "running": 2
  },
  "facets": {
    "agent": {
      "claude": 5,
      "codex": 8
    },
    "origin": {
      "human": 8,
      "scheduled": 1,
      "subagent": 3,
      "review": 1
    },
    "status": {
      "running": 2,
      "finished": 4,
      "failed": 2,
      "unknown": 5
    },
    "project": [
      [
        "/work/gamma",
        8
      ],
      [
        "/work/alpha",
        1
      ],
      [
        "/work/beta",
        1
      ]
    ]
  },
  "progress": {
    "state": "idle",
    "total": 13,
    "summarized": 13,
    "from_cache": 13,
    "read": 0,
    "failed": 0,
    "complete": true
  },
  "freshness": {
    "fast_pass_at": 1800000000.0,
    "summary_pass_at": 1800000000.0,
    "passes": 2
  },
  "cache": {
    "state": "ok",
    "write_errors": 0
  },
  "sessions": [
    {
      "agent": "claude",
      "session_id": "11111111-1111-4111-8111-111111111111",
      "home": ".claude",
      "title": "Synthetic session",
      "parent_id": null,
      "child_ids": [
        "agent-aaa"
      ],
      "origin": "human",
      "project": "/work/alpha",
      "git_branch": "main",
      "started_at": 1799913600.0,
      "ended_at": 1799913631.0,
      "last_activity": 1799913640.0,
      "duration_seconds": 31.0,
      "size_bytes": 3346,
      "records": 17,
      "replayed_records": 2,
      "turns": 2,
      "models": [
        "claude-test-1",
        "claude-test-2"
      ],
      "status": "finished",
      "summarized": true,
      "source_paths": [
        ".claude/projects/-work-alpha/11111111-1111-4111-8111-111111111111.jsonl"
      ]
    },
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000008",
      "home": ".codex",
      "title": "title 8",
      "parent_id": null,
      "child_ids": [],
      "origin": "human",
      "project": "/work/gamma",
      "git_branch": "main",
      "started_at": 1799994400.0,
      "ended_at": null,
      "last_activity": 1799995000.0,
      "duration_seconds": null,
      "size_bytes": 2832,
      "records": 21,
      "replayed_records": 0,
      "turns": 0,
      "models": [
        "gpt-test-1"
      ],
      "status": "unknown",
      "summarized": true,
      "source_paths": [
        ".codex/root/.codex/sessions/2026/11/18/rollout-2026-11-18T04-00-00-00000000-0000-4000-8000-000000000008.jsonl"
      ]
    }
  ]
}
? 0
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/sessions?sync=1&now=1800000000&sort=size&limit=2&offset=2'
api: /api/plugin/agents/sessions?sync=1&now=1800000000&sort=size&limit=2&offset=2
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "filters": {
    "agent": null,
    "origin": [],
    "status": [],
    "project": null,
    "model": null,
    "since": null,
    "until": null
  },
  "sort": "size",
  "order": "desc",
  "offset": 2,
  "limit": 2,
  "next_offset": 4,
  "total": 13,
  "available": 13,
  "totals": {
    "size_bytes": 7642,
    "running": 2
  },
  "facets": {
    "agent": {
      "claude": 5,
      "codex": 8
    },
    "origin": {
      "human": 8,
      "scheduled": 1,
      "subagent": 3,
      "review": 1
    },
    "status": {
      "running": 2,
      "finished": 4,
      "failed": 2,
      "unknown": 5
    },
    "project": [
      [
        "/work/gamma",
        8
      ],
      [
        "/work/alpha",
        1
      ],
      [
        "/work/beta",
        1
      ]
    ]
  },
  "progress": {
    "state": "idle",
    "total": 13,
    "summarized": 13,
    "from_cache": 13,
    "read": 0,
    "failed": 0,
    "complete": true
  },
  "freshness": {
    "fast_pass_at": 1800000000.0,
    "summary_pass_at": 1800000000.0,
    "passes": 2
  },
  "cache": {
    "state": "ok",
    "write_errors": 0
  },
  "sessions": [
    {
      "agent": "claude",
      "session_id": "22222222-2222-4222-8222-222222222222",
      "home": ".claude",
      "title": null,
      "parent_id": null,
      "child_ids": [],
      "origin": "scheduled",
      "project": "/work/beta",
      "git_branch": "dev",
      "started_at": 1799917200.0,
      "ended_at": 1799917201.0,
      "last_activity": 1799917201.0,
      "duration_seconds": 1.0,
      "size_bytes": 471,
      "records": 2,
      "replayed_records": 0,
      "turns": 1,
      "models": [],
      "status": "failed",
      "summarized": true,
      "source_paths": [
        ".claude/projects/-work-alpha/22222222-2222-4222-8222-222222222222.jsonl"
      ]
    },
    {
      "agent": "claude",
      "session_id": "agent-aaa",
      "home": ".claude",
      "title": "Explore code",
      "parent_id": "11111111-1111-4111-8111-111111111111",
      "child_ids": [
        "agent-bbb"
      ],
      "origin": "subagent",
      "project": null,
      "git_branch": null,
      "started_at": 1799913621.0,
      "ended_at": 1799913625.0,
      "last_activity": 1799913626.0,
      "duration_seconds": 4.0,
      "size_bytes": 467,
      "records": 2,
      "replayed_records": 0,
      "turns": 1,
      "models": [
        "claude-sub-1"
      ],
      "status": "finished",
      "summarized": true,
      "source_paths": [
        ".claude/projects/-work-alpha/11111111-1111-4111-8111-111111111111/subagents/agent-aaa.jsonl"
      ]
    }
  ]
}
? 0
```

## Test: a time range and a project

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/sessions?sync=1&now=1800000000&project=/work/beta&since=1799900000&until=1799999999&limit=5'
api: /api/plugin/agents/sessions?sync=1&now=1800000000&project=/work/beta&since=1799900000&until=1799999999&limit=5
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "filters": {
    "agent": null,
    "origin": [],
    "status": [],
    "project": "/work/beta",
    "model": null,
    "since": 1799900000.0,
    "until": 1799999999.0
  },
  "sort": "activity",
  "order": "desc",
  "offset": 0,
  "limit": 5,
  "next_offset": null,
  "total": 1,
  "available": 13,
  "totals": {
    "size_bytes": 471,
    "running": 0
  },
  "facets": {
    "agent": {
      "claude": 5,
      "codex": 8
    },
    "origin": {
      "human": 8,
      "scheduled": 1,
      "subagent": 3,
      "review": 1
    },
    "status": {
      "running": 2,
      "finished": 4,
      "failed": 2,
      "unknown": 5
    },
    "project": [
      [
        "/work/gamma",
        8
      ],
      [
        "/work/alpha",
        1
      ],
      [
        "/work/beta",
        1
      ]
    ]
  },
  "progress": {
    "state": "idle",
    "total": 13,
    "summarized": 13,
    "from_cache": 13,
    "read": 0,
    "failed": 0,
    "complete": true
  },
  "freshness": {
    "fast_pass_at": 1800000000.0,
    "summary_pass_at": 1800000000.0,
    "passes": 2
  },
  "cache": {
    "state": "ok",
    "write_errors": 0
  },
  "sessions": [
    {
      "agent": "claude",
      "session_id": "22222222-2222-4222-8222-222222222222",
      "home": ".claude",
      "title": null,
      "parent_id": null,
      "child_ids": [],
      "origin": "scheduled",
      "project": "/work/beta",
      "git_branch": "dev",
      "started_at": 1799917200.0,
      "ended_at": 1799917201.0,
      "last_activity": 1799917201.0,
      "duration_seconds": 1.0,
      "size_bytes": 471,
      "records": 2,
      "replayed_records": 0,
      "turns": 1,
      "models": [],
      "status": "failed",
      "summarized": true,
      "source_paths": [
        ".claude/projects/-work-alpha/22222222-2222-4222-8222-222222222222.jsonl"
      ]
    }
  ]
}
? 0
```

## Test: an unavailable cache directory still answers, uncached

The cache directory here is a regular file, so no private directory can be made.
The catalog is built in memory and says so.

```console
$ METABROWSER_CACHE_DIR=$PWD/cache-is-a-file metab root --api '/api/plugin/agents/sessions?sync=1&now=1800000000&limit=1'
api: /api/plugin/agents/sessions?sync=1&now=1800000000&limit=1
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "filters": {
    "agent": null,
    "origin": [],
    "status": [],
    "project": null,
    "model": null,
    "since": null,
    "until": null
  },
  "sort": "activity",
  "order": "desc",
  "offset": 0,
  "limit": 1,
  "next_offset": 1,
  "total": 13,
  "available": 13,
  "totals": {
    "size_bytes": 7642,
    "running": 2
  },
  "facets": {
    "agent": {
      "claude": 5,
      "codex": 8
    },
    "origin": {
      "human": 8,
      "scheduled": 1,
      "subagent": 3,
      "review": 1
    },
    "status": {
      "running": 2,
      "finished": 4,
      "failed": 2,
      "unknown": 5
    },
    "project": [
      [
        "/work/gamma",
        8
      ],
      [
        "/work/alpha",
        1
      ],
      [
        "/work/beta",
        1
      ]
    ]
  },
  "progress": {
    "state": "idle",
    "total": 13,
    "summarized": 13,
    "from_cache": 0,
    "read": 13,
    "failed": 0,
    "complete": true
  },
  "freshness": {
    "fast_pass_at": 1800000000.0,
    "summary_pass_at": 1800000000.0,
    "passes": 2
  },
  "cache": {
    "state": "unavailable",
    "write_errors": 0
  },
  "sessions": [
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000005",
      "home": ".codex",
      "title": "title 5",
      "parent_id": null,
      "child_ids": [],
      "origin": "human",
      "project": "/work/gamma",
      "git_branch": "main",
      "started_at": 1799999370.0,
      "ended_at": null,
      "last_activity": 1799999970.0,
      "duration_seconds": null,
      "size_bytes": 0,
      "records": 0,
      "replayed_records": 0,
      "turns": 0,
      "models": [
        "gpt-test-1"
      ],
      "status": "running",
      "summarized": true,
      "source_paths": []
    }
  ]
}
? 0
```

## Test: refusals are typed JSON

A bad parameter is a 400 naming the parameter; a missing folder or session is a 404.

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/sessions?sync=1&now=1800000000&sort=mood'
api: /api/plugin/agents/sessions?sync=1&now=1800000000&sort=mood
status: 400
{
  "error": "sort must be one of: activity, start, duration, turns, records, size, title, agent, origin, project, status, model",
  "code": "bad_param",
  "param": "sort"
}
Error: /api/plugin/agents/sessions?sync=1&now=1800000000&sort=mood returned HTTP 400
? 1
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/sessions?sync=1&now=1800000000&limit=100000'
api: /api/plugin/agents/sessions?sync=1&now=1800000000&limit=100000
status: 400
{
  "error": "limit must be between 1 and 500",
  "code": "bad_param",
  "param": "limit"
}
Error: /api/plugin/agents/sessions?sync=1&now=1800000000&limit=100000 returned HTTP 400
? 1
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/catalog?folder=plain'
api: /api/plugin/agents/catalog?folder=plain
status: 404
{
  "error": "This folder holds no Claude Code or Codex home",
  "code": "no_agent_homes",
  "param": "folder"
}
Error: /api/plugin/agents/catalog?folder=plain returned HTTP 404
? 1
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/catalog?folder=missing'
api: /api/plugin/agents/catalog?folder=missing
status: 404
{
  "error": "No such folder",
  "code": "not_found",
  "param": "folder"
}
Error: /api/plugin/agents/catalog?folder=missing returned HTTP 404
? 1
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/session?sync=1&now=1800000000&agent=codex&id=nope'
api: /api/plugin/agents/session?sync=1&now=1800000000&agent=codex&id=nope
status: 404
{
  "error": "No such session",
  "code": "session_not_found",
  "param": "id"
}
Error: /api/plugin/agents/session?sync=1&now=1800000000&agent=codex&id=nope returned HTTP 404
? 1
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/records?agent=claude'
api: /api/plugin/agents/records?agent=claude
status: 400
{
  "error": "name a session with path, or with agent and id",
  "code": "bad_param",
  "param": "id"
}
Error: /api/plugin/agents/records?agent=claude returned HTTP 400
? 1
```
