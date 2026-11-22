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
  > fixture.log 2>&1
---
# Golden tests: one session, its records, and what is live, through `--api`

The `session`, `records`, and `live` routes of the `agents` plugin, over the homes
`tests/agents_synthetic_home.py` writes under `root`.
`cli-api-agents-catalog.tryscript.md` pins the catalog and the session list; the
commands here pass `sync=1` and `now=1800000000` for the same reason, and name a cache
directory so the first run fills it.

## Test: one session with its children

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/session?sync=1&now=1800000000&agent=claude&id=11111111-1111-4111-8111-111111111111'
api: /api/plugin/agents/session?sync=1&now=1800000000&agent=claude&id=11111111-1111-4111-8111-111111111111
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "session": {
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
  "parent": null,
  "children": [
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
  ],
  "children_total": 1,
  "drift": {
    "clean": false,
    "unknown_types": {
      "assistant/hologram": 1,
      "never-seen-type": 1
    },
    "unexpected_columns": {},
    "missing_columns": {},
    "read_errors": {},
    "truncated": false
  },
  "provider_sections": [],
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
  }
}
? 0
```

## Test: a child session names its parent

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/session?sync=1&now=1800000000&agent=claude&id=agent-aaa'
api: /api/plugin/agents/session?sync=1&now=1800000000&agent=claude&id=agent-aaa
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "session": {
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
  "parent": {
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
  "children": [
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
  ],
  "children_total": 1,
  "drift": {
    "clean": true,
    "unknown_types": {},
    "unexpected_columns": {},
    "missing_columns": {},
    "read_errors": {},
    "truncated": false
  },
  "provider_sections": [],
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
    "fast_pass_at": [..],
    "summary_pass_at": [..],
    "passes": 2
  }
}
? 0
```

## Test: a session found by its source file

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/session?sync=1&now=1800000000&path=.claude/projects/-work-alpha/22222222-2222-4222-8222-222222222222.jsonl'
api: /api/plugin/agents/session?sync=1&now=1800000000&path=.claude/projects/-work-alpha/22222222-2222-4222-8222-222222222222.jsonl
status: 200
{
  "folder": ".claude",
  "now": 1800000000.0,
  "session": {
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
  "parent": null,
  "children": [],
  "children_total": 0,
  "drift": {
    "clean": true,
    "unknown_types": {},
    "unexpected_columns": {},
    "missing_columns": {},
    "read_errors": {},
    "truncated": false
  },
  "provider_sections": [],
  "progress": {
    "state": "idle",
    "total": 5,
    "summarized": 5,
    "from_cache": 5,
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

## Test: a Codex thread with a spawned child

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/session?sync=1&now=1800000000&agent=codex&id=00000000-0000-4000-8000-000000000001'
api: /api/plugin/agents/session?sync=1&now=1800000000&agent=codex&id=00000000-0000-4000-8000-000000000001
status: 200
{
  "folder": "",
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
    "total": 13,
    "summarized": 13,
    "from_cache": 13,
    "read": 0,
    "failed": 0,
    "complete": true
  },
  "freshness": {
    "fast_pass_at": [..],
    "summary_pass_at": [..],
    "passes": 2
  }
}
? 0
```

## Test: records filtered by kind

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/records?sync=1&now=1800000000&agent=claude&id=11111111-1111-4111-8111-111111111111&kind=tool-call'
api: /api/plugin/agents/records?sync=1&now=1800000000&agent=claude&id=11111111-1111-4111-8111-111111111111&kind=tool-call
status: 200
{
  "folder": "",
  "session": {
    "agent": "claude",
    "session_id": "11111111-1111-4111-8111-111111111111",
    "home": ".claude"
  },
  "filters": {
    "kind": "tool-call",
    "tool": null,
    "locator": null
  },
  "cursor": 0,
  "limit": 200,
  "examined": 24,
  "next_cursor": null,
  "truncated": false,
  "events": [
    {
      "session_id": "11111111-1111-4111-8111-111111111111",
      "ordinal": 6,
      "locator": "6.2",
      "timestamp": 1799913612.0,
      "kind": "tool-call",
      "raw_type": "assistant",
      "raw_subtype": "tool_use",
      "tool_name": "Bash",
      "tool_family": "shell",
      "summary": "Bash: ls",
      "replay": false
    },
    {
      "session_id": "11111111-1111-4111-8111-111111111111",
      "ordinal": 11,
      "locator": "11.0",
      "timestamp": 1799913620.0,
      "kind": "tool-call",
      "raw_type": "assistant",
      "raw_subtype": "tool_use",
      "tool_name": "Task",
      "tool_family": "subagent",
      "summary": "Task: Explore",
      "replay": false
    },
    {
      "session_id": "11111111-1111-4111-8111-111111111111",
      "ordinal": 11,
      "locator": "11.1",
      "timestamp": 1799913620.0,
      "kind": "tool-call",
      "raw_type": "assistant",
      "raw_subtype": "tool_use",
      "tool_name": "mcp:srv.lookup",
      "tool_family": "mcp",
      "summary": "mcp__srv__lookup",
      "replay": false
    }
  ]
}
? 0
```

## Test: records filtered by tool

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/records?sync=1&now=1800000000&agent=claude&id=11111111-1111-4111-8111-111111111111&tool=Bash'
api: /api/plugin/agents/records?sync=1&now=1800000000&agent=claude&id=11111111-1111-4111-8111-111111111111&tool=Bash
status: 200
{
  "folder": "",
  "session": {
    "agent": "claude",
    "session_id": "11111111-1111-4111-8111-111111111111",
    "home": ".claude"
  },
  "filters": {
    "kind": null,
    "tool": "Bash",
    "locator": null
  },
  "cursor": 0,
  "limit": 200,
  "examined": 24,
  "next_cursor": null,
  "truncated": false,
  "events": [
    {
      "session_id": "11111111-1111-4111-8111-111111111111",
      "ordinal": 6,
      "locator": "6.2",
      "timestamp": 1799913612.0,
      "kind": "tool-call",
      "raw_type": "assistant",
      "raw_subtype": "tool_use",
      "tool_name": "Bash",
      "tool_family": "shell",
      "summary": "Bash: ls",
      "replay": false
    },
    {
      "session_id": "11111111-1111-4111-8111-111111111111",
      "ordinal": 7,
      "locator": "7.0",
      "timestamp": 1799913614.0,
      "kind": "tool-result",
      "raw_type": "user",
      "raw_subtype": "tool_result",
      "tool_name": "Bash",
      "tool_family": "shell",
      "summary": "result",
      "replay": false
    }
  ]
}
? 0
```

## Test: records in pages, with a cursor

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/records?sync=1&now=1800000000&agent=codex&id=00000000-0000-4000-8000-000000000001&limit=3'
api: /api/plugin/agents/records?sync=1&now=1800000000&agent=codex&id=00000000-0000-4000-8000-000000000001&limit=3
status: 200
{
  "folder": "",
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
  "limit": 3,
  "examined": 3,
  "next_cursor": 3,
  "truncated": false,
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
    }
  ]
}
? 0
```

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/records?sync=1&now=1800000000&agent=codex&id=00000000-0000-4000-8000-000000000001&limit=3&cursor=3'
api: /api/plugin/agents/records?sync=1&now=1800000000&agent=codex&id=00000000-0000-4000-8000-000000000001&limit=3&cursor=3
status: 200
{
  "folder": "",
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
  "cursor": 3,
  "limit": 3,
  "examined": 6,
  "next_cursor": 6,
  "truncated": false,
  "events": [
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
    },
    {
      "session_id": "00000000-0000-4000-8000-000000000001",
      "ordinal": 6,
      "locator": "00000000-0000-4000-8000-000000000001:6",
      "timestamp": 1799913706.0,
      "kind": "tool-call",
      "raw_type": "thread_item",
      "raw_subtype": "mcpToolCall",
      "tool_name": "mcp:srv.lookup",
      "tool_family": "mcp",
      "summary": "mcp:srv.lookup",
      "replay": false
    },
    {
      "session_id": "00000000-0000-4000-8000-000000000001",
      "ordinal": 7,
      "locator": "00000000-0000-4000-8000-000000000001:7",
      "timestamp": 1799913707.0,
      "kind": "tool-call",
      "raw_type": "thread_item",
      "raw_subtype": "fileChange",
      "tool_name": "fileChange",
      "tool_family": "edit",
      "summary": "fileChange",
      "replay": false
    }
  ]
}
? 0
```

## Test: records of one locator

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/records?sync=1&now=1800000000&agent=claude&id=11111111-1111-4111-8111-111111111111&locator=5.0'
api: /api/plugin/agents/records?sync=1&now=1800000000&agent=claude&id=11111111-1111-4111-8111-111111111111&locator=5.0
status: 200
{
  "folder": "",
  "session": {
    "agent": "claude",
    "session_id": "11111111-1111-4111-8111-111111111111",
    "home": ".claude"
  },
  "filters": {
    "kind": null,
    "tool": null,
    "locator": "5.0"
  },
  "cursor": 0,
  "limit": 200,
  "examined": 24,
  "next_cursor": null,
  "truncated": false,
  "events": [
    {
      "session_id": "11111111-1111-4111-8111-111111111111",
      "ordinal": 5,
      "locator": "5.0",
      "timestamp": 1799913610.0,
      "kind": "prompt",
      "raw_type": "user",
      "raw_subtype": "text",
      "tool_name": null,
      "tool_family": null,
      "summary": "Please list files",
      "replay": false
    }
  ]
}
? 0
```

## Test: live sessions

```console
$ METABROWSER_CACHE_DIR=$PWD/cache metab root --api '/api/plugin/agents/live?sync=1&now=1800000000'
api: /api/plugin/agents/live?sync=1&now=1800000000
status: 200
{
  "folder": "",
  "now": 1800000000.0,
  "total": 2,
  "sessions": [
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000006",
      "home": ".codex",
      "source": "active-chat-turn",
      "status": "busy",
      "project": "/work/gamma",
      "name": "title 6",
      "title": "title 6",
      "models": [
        "gpt-test-1"
      ],
      "started_at": 1799998800.0,
      "source_paths": [],
      "pid": null,
      "updated_at": 1799999980.0
    },
    {
      "agent": "codex",
      "session_id": "00000000-0000-4000-8000-000000000005",
      "home": ".codex",
      "source": "recent-update",
      "status": "idle",
      "project": "/work/gamma",
      "name": "title 5",
      "title": "title 5",
      "models": [
        "gpt-test-1"
      ],
      "started_at": 1799999370.0,
      "source_paths": [],
      "pid": null,
      "updated_at": 1799999970.0
    }
  ]
}
? 0
```
