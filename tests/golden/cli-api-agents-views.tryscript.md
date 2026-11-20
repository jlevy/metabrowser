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
  mkdir root/loose &&
  printf '{"type":"user"}\n' > root/loose/export.jsonl
---
# Golden tests: what the agents views ask the routes for

The agents home, the session list, and the Session view each read the `catalog`,
`sessions`, `session`, `records`, and `live` routes.
Their data semantics (which sessions, in what order, how many) are the routes', and
`cli-api-agents-catalog.tryscript.md` and `cli-api-agents-sessions.tryscript.md` pin
them over the synthetic homes.
This transcript pins the two requests those transcripts leave out: the session list as
it opens, and a compressed Codex rollout opened as a session.

The list opens without automatic reviews, which are most Codex threads, so its first
request names every other origin (`tests/dom/agents-views-session.js` prints the same
query from the list’s state).
The synthetic homes hold one review thread, so the list’s total is one less than the
folder’s.

## Test: the session list as it opens

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/sessions?sync=1&now=1800000000&sort=activity&order=desc&limit=50&origin=human%2Cscheduled%2Csubagent%2Cautomation'
api: /api/plugin/agents/sessions?sync=1&now=1800000000&sort=activity&order=desc&limit=50&origin=human%2Cscheduled%2Csubagent%2Cautomation
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "filters": {
    "agent": null,
    "origin": [
      "human",
      "scheduled",
      "subagent",
      "automation"
    ],
    "status": [],
    "project": null,
    "model": null,
    "since": null,
    "until": null
  },
  "sort": "activity",
  "order": "desc",
  "offset": 0,
  "limit": 50,
  "next_offset": null,
  "total": 12,
  "available": 13,
  "totals": {
    "size_bytes": 7612,
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
    ],
    "model": [
      [
        "gpt-test-1",
        7
      ],
      [
        "claude-sub-1",
        1
      ],
      [
        "claude-sub-2",
        1
      ],
      [
        "claude-test-1",
        1
      ],
      [
        "claude-test-2",
        1
      ],
      [
        "gpt-test-2",
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
    "fast_pass_at": [..],
    "summary_pass_at": [..],
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
    },
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000004",
      "home": ".codex",
      "title": "title 4",
      "parent_id": null,
      "child_ids": [],
      "origin": "human",
      "project": "/work/gamma",
      "git_branch": "main",
      "started_at": 1799997600.0,
      "ended_at": 1799998200.0,
      "last_activity": 1799998200.0,
      "duration_seconds": 600.0,
      "size_bytes": 120,
      "records": 4,
      "replayed_records": 0,
      "turns": 2,
      "models": [
        "gpt-test-2"
      ],
      "status": "finished",
      "summarized": true,
      "source_paths": [
        "root/.codex/sessions/2026/11/18/rollout-2026-11-18T02-00-00-00000000-0000-4000-8000-000000000004.jsonl.zst",
        "root/.codex/sessions/2026/11/18/rollout-2026-11-18T03-00-00-00000000-0000-4000-8000-000000000004_00000000-0000-4000-8000-0000000000a4.jsonl.zst"
      ]
    },
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000002",
      "home": ".codex",
      "title": "title 2",
      "parent_id": "00000000-0000-4000-8000-000000000001",
      "child_ids": [],
      "origin": "subagent",
      "project": "/work/gamma",
      "git_branch": "main",
      "started_at": 1799995900.0,
      "ended_at": null,
      "last_activity": 1799996500.0,
      "duration_seconds": null,
      "size_bytes": 0,
      "records": 1,
      "replayed_records": 0,
      "turns": 0,
      "models": [
        "gpt-test-1"
      ],
      "status": "unknown",
      "summarized": true,
      "source_paths": []
    },
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000001",
      "home": ".codex",
      "title": "Gamma thread",
      "parent_id": null,
      "child_ids": [
        "00000000-0000-4000-8000-000000000002"
      ],
      "origin": "human",
      "project": "/work/gamma",
      "git_branch": "main",
      "started_at": 1799995800.0,
      "ended_at": 1799996400.0,
      "last_activity": 1799996400.0,
      "duration_seconds": 600.0,
      "size_bytes": 40,
      "records": 11,
      "replayed_records": 0,
      "turns": 2,
      "models": [
        "gpt-test-1"
      ],
      "status": "failed",
      "summarized": true,
      "source_paths": [
        "root/.codex/sessions/2026/11/18/rollout-2026-11-18T00-00-00-00000000-0000-4000-8000-000000000001.jsonl.zst"
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
        "root/.codex/sessions/2026/11/18/rollout-2026-11-18T04-00-00-00000000-0000-4000-8000-000000000008.jsonl"
      ]
    },
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
    },
    {
      "agent": "claude",
      "session_id": "33333333-3333-4333-8333-333333333333",
      "home": ".claude",
      "title": null,
      "parent_id": null,
      "child_ids": [],
      "origin": "human",
      "project": null,
      "git_branch": null,
      "started_at": null,
      "ended_at": null,
      "last_activity": 1799913610.0,
      "duration_seconds": null,
      "size_bytes": 100,
      "records": null,
      "replayed_records": 0,
      "turns": null,
      "models": [],
      "status": "unknown",
      "summarized": true,
      "source_paths": [
        ".claude/projects/-work-alpha/33333333-3333-4333-8333-333333333333.jsonl.zst"
      ]
    },
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000007",
      "home": ".codex",
      "title": "title 7",
      "parent_id": null,
      "child_ids": [],
      "origin": "human",
      "project": "/work/gamma",
      "git_branch": "main",
      "started_at": 1799909400.0,
      "ended_at": null,
      "last_activity": 1799910000.0,
      "duration_seconds": null,
      "size_bytes": 0,
      "records": 0,
      "replayed_records": 0,
      "turns": 1,
      "models": [
        "gpt-test-1"
      ],
      "status": "unknown",
      "summarized": true,
      "source_paths": []
    }
  ]
}
? 0
```

## Test: a compressed rollout opens as its thread’s session

A rollout Codex has compressed holds no readable bytes for Metabrowser, so the Session
view asks for its thread by the file’s own path, and the events come from the thread’s
history store.

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/session?sync=1&now=1800000000&path=.codex/sessions/2026/11/18/rollout-2026-11-18T00-00-00-00000000-0000-4000-8000-000000000001.jsonl.zst'
api: /api/plugin/agents/session?sync=1&now=1800000000&path=.codex/sessions/2026/11/18/rollout-2026-11-18T00-00-00-00000000-0000-4000-8000-000000000001.jsonl.zst
status: 200
{
  "folder": ".codex",
  "now": 1800000000.0,
  "session": {
    "agent": "codex",
    "session_id": "00000000-0000-4000-8000-000000000001",
    "home": ".codex",
    "title": "Gamma thread",
    "parent_id": null,
    "child_ids": [
      "00000000-0000-4000-8000-000000000002"
    ],
    "origin": "human",
    "project": "/work/gamma",
    "git_branch": "main",
    "started_at": 1799995800.0,
    "ended_at": 1799996400.0,
    "last_activity": 1799996400.0,
    "duration_seconds": 600.0,
    "size_bytes": 40,
    "records": 11,
    "replayed_records": 0,
    "turns": 2,
    "models": [
      "gpt-test-1"
    ],
    "status": "failed",
    "summarized": true,
    "source_paths": [
      ".codex/root/.codex/sessions/2026/11/18/rollout-2026-11-18T00-00-00-00000000-0000-4000-8000-000000000001.jsonl.zst"
    ]
  },
  "parent": null,
  "children": [
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000002",
      "home": ".codex",
      "title": "title 2",
      "parent_id": "00000000-0000-4000-8000-000000000001",
      "child_ids": [],
      "origin": "subagent",
      "project": "/work/gamma",
      "git_branch": "main",
      "started_at": 1799995900.0,
      "ended_at": null,
      "last_activity": 1799996500.0,
      "duration_seconds": null,
      "size_bytes": 0,
      "records": 1,
      "replayed_records": 0,
      "turns": 0,
      "models": [
        "gpt-test-1"
      ],
      "status": "unknown",
      "summarized": true,
      "source_paths": []
    }
  ],
  "children_total": 1,
  "drift": {
    "clean": false,
    "unknown_types": {
      "thread_item/holographicThing": 1
    },
    "unexpected_columns": {
      "history.thread_items.zz_new_col": 1,
      "state.threads.zz_future": 1
    },
    "missing_columns": {},
    "read_errors": {},
    "truncated": false
  },
  "provider_sections": [],
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
    "fast_pass_at": [..],
    "summary_pass_at": [..],
    "passes": 1
  }
}
? 0
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/records?sync=1&now=1800000000&limit=4&path=.codex/sessions/2026/11/18/rollout-2026-11-18T00-00-00-00000000-0000-4000-8000-000000000001.jsonl.zst'
api: /api/plugin/agents/records?sync=1&now=1800000000&limit=4&path=.codex/sessions/2026/11/18/rollout-2026-11-18T00-00-00-00000000-0000-4000-8000-000000000001.jsonl.zst
status: 200
{
  "folder": ".codex",
  "session": {
    "agent": "codex",
    "session_id": "00000000-0000-4000-8000-000000000001",
    "home": ".codex"
  },
  "filters": {
    "kind": null,
    "tool": null,
    "locator": null
  },
  "cursor": 0,
  "limit": 4,
  "examined": 4,
  "next_cursor": 4,
  "events": [
    {
      "session_id": "00000000-0000-4000-8000-000000000001",
      "ordinal": 2,
      "locator": "00000000-0000-4000-8000-000000000001:2",
      "timestamp": 1799913702.0,
      "kind": "prompt",
      "raw_type": "thread_item",
      "raw_subtype": "userMessage",
      "tool_name": null,
      "tool_family": null,
      "summary": "hello codex",
      "replay": false
    },
    {
      "session_id": "00000000-0000-4000-8000-000000000001",
      "ordinal": 3,
      "locator": "00000000-0000-4000-8000-000000000001:3",
      "timestamp": 1799913703.0,
      "kind": "thinking",
      "raw_type": "thread_item",
      "raw_subtype": "reasoning",
      "tool_name": null,
      "tool_family": null,
      "summary": "thinking it over",
      "replay": false
    },
    {
      "session_id": "00000000-0000-4000-8000-000000000001",
      "ordinal": 4,
      "locator": "00000000-0000-4000-8000-000000000001:4",
      "timestamp": 1799913704.0,
      "kind": "text",
      "raw_type": "thread_item",
      "raw_subtype": "agentMessage",
      "tool_name": null,
      "tool_family": null,
      "summary": "hello human",
      "replay": false
    },
    {
      "session_id": "00000000-0000-4000-8000-000000000001",
      "ordinal": 5,
      "locator": "00000000-0000-4000-8000-000000000001:5",
      "timestamp": 1799913705.0,
      "kind": "tool-call",
      "raw_type": "thread_item",
      "raw_subtype": "commandExecution",
      "tool_name": "commandExecution",
      "tool_family": "shell",
      "summary": "ls -l (exit 0)",
      "replay": false
    }
  ]
}
? 0
```

## Test: a transcript outside every agent home says so

A file in no agent home, an exported transcript for one, has no session, and the Session
view falls back to the Log it always had.
The route says why, in a typed refusal.

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/session?sync=1&now=1800000000&path=loose/export.jsonl'
api: /api/plugin/agents/session?sync=1&now=1800000000&path=loose/export.jsonl
status: 404
{
  "error": "This file is not inside an agent home",
  "code": "no_agent_homes",
  "param": "path"
}
Error: /api/plugin/agents/session?sync=1&now=1800000000&path=loose/export.jsonl returned HTTP 404
? 1
```

## Test: the home and the list are offered where a folder holds a home

A folder that is, or holds, a Claude Code or Codex home offers the Agents and Sessions
views, and Agents is then its default.
A folder inside a home that is not itself one has neither.

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --show .
show: .
route: /view/
kind: folder
views: agents (default, key A), agent-sessions (key S), overview (key O), treemap (key M)
model: folder envelope; readme_path=
? 0
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --show .claude/projects
show: .claude/projects
route: /view/.claude/projects
kind: folder
views: overview (default, key O), treemap (key M)
model: folder envelope; readme_path=
? 0
```

## Test: a compressed rollout is an agent thread

Metabrowser reads no zstd, so the file’s kind is claimed by its path, and it opens on
its Session view.

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --show .codex/sessions/2026/11/18/rollout-2026-11-18T00-00-00-00000000-0000-4000-8000-000000000001.jsonl.zst
show: .codex/sessions/2026/11/18/rollout-2026-11-18T00-00-00-00000000-0000-4000-8000-000000000001.jsonl.zst
route: /view/.codex/sessions/2026/11/18/rollout-2026-11-18T00-00-00-00000000-0000-4000-8000-000000000001.jsonl.zst
kind: agent-thread
views: session (default, key E), log (key V)
model: binary envelope; size=40
? 0
```
