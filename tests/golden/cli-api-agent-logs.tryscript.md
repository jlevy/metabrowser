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
  mkdir root &&
  cp "$TRYSCRIPT_TEST_DIR/../fixtures/agent-logs/claude-transcript.jsonl"
  "$TRYSCRIPT_TEST_DIR/../fixtures/agent-logs/codex-rollout.jsonl" root/
---
# Golden tests: Claude Code transcripts and Codex rollouts

A Claude Code session transcript opens with queue operations, attachments, and session
metadata, and its first `assistant` record comes after line 20. A Codex rollout wraps
each record in a `{timestamp, ordinal, type, payload}` envelope.
Both are agent logs, with the Log, Charts, and Raw JSON views.
The fixtures are synthetic; `tests/test_agent_log_formats.py` pins the parsed events.

## Test: a Claude Code session transcript

```console
$ metab root --show claude-transcript.jsonl
show: claude-transcript.jsonl
route: /view/claude-transcript.jsonl
kind: agent-log
views: log (default, key V), charts (key C), raw (key S)
model: jsonl envelope; size=10570
? 0
```

## Test: a Codex rollout

```console
$ metab root --show codex-rollout.jsonl
show: codex-rollout.jsonl
route: /view/codex-rollout.jsonl
kind: agent-log
views: log (default, key V), charts (key C), raw (key S)
model: jsonl envelope; size=6611
? 0
```

## Test: the transcript’s chart counts

Records without conversation count as `system`; each content block counts once.

```console
$ metab root --api '/api/plugin/agent-log/charts?path=claude-transcript.jsonl'
api: /api/plugin/agent-log/charts?path=claude-transcript.jsonl
status: 200
{
  "summary": {
    "counts": {
      "system": 25,
      "text": 2,
      "thinking": 1,
      "tool_call/Bash": 1,
      "tool_result/success": 1
    },
    "metadata": {
      "adapter": "claude"
    }
  },
  "charts": [
    {
      "id": "event-activity",
      "title": "Event Activity",
      "type": "stacked-bar",
      "x_type": "time",
      "y_label": "events",
      "bin_seconds": 10,
      "series": [
        {
          "label": "system",
          "color": "var(--agent-log-kind-muted-text)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 20
            }
          ]
        },
        {
          "label": "text",
          "color": "var(--agent-log-kind-neutral-text)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 2
            }
          ]
        },
        {
          "label": "thinking",
          "color": "var(--agent-log-kind-thinking-text)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 1
            }
          ]
        },
        {
          "label": "tool_call",
          "color": "var(--agent-log-kind-tool-text)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 1
            }
          ]
        },
        {
          "label": "tool_result",
          "color": "var(--agent-log-kind-tool-result-fill)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 1
            }
          ]
        }
      ]
    }
  ]
}
? 0
```

## Test: the rollout’s chart counts

Commands run inside Codex’s `exec` tool count as tool calls of their own.

```console
$ metab root --api '/api/plugin/agent-log/charts?path=codex-rollout.jsonl'
api: /api/plugin/agent-log/charts?path=codex-rollout.jsonl
status: 200
{
  "summary": {
    "counts": {
      "init": 1,
      "system": 6,
      "text": 2,
      "thinking": 1,
      "tool_call/exec": 1,
      "tool_call/command": 2,
      "tool_result/success": 2,
      "tool_call/spawn_agent": 1,
      "tool_call/file_change": 1,
      "tool_call/mcp:docs.search": 1,
      "result/done": 2
    },
    "metadata": {
      "adapter": "codex-rollout",
      "duration": "8s"
    }
  },
  "charts": [
    {
      "id": "event-activity",
      "title": "Event Activity",
      "type": "stacked-bar",
      "x_type": "time",
      "y_label": "events",
      "bin_seconds": 10,
      "series": [
        {
          "label": "init",
          "color": "var(--agent-log-kind-init-text)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 1
            },
            {
              "x": "2026-11-19T10:00:10+00:00",
              "y": 0
            }
          ]
        },
        {
          "label": "system",
          "color": "var(--agent-log-kind-muted-text)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 5
            },
            {
              "x": "2026-11-19T10:00:10+00:00",
              "y": 1
            }
          ]
        },
        {
          "label": "text",
          "color": "var(--agent-log-kind-neutral-text)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 2
            },
            {
              "x": "2026-11-19T10:00:10+00:00",
              "y": 0
            }
          ]
        },
        {
          "label": "thinking",
          "color": "var(--agent-log-kind-thinking-text)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 1
            },
            {
              "x": "2026-11-19T10:00:10+00:00",
              "y": 0
            }
          ]
        },
        {
          "label": "tool_call",
          "color": "var(--agent-log-kind-tool-text)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 6
            },
            {
              "x": "2026-11-19T10:00:10+00:00",
              "y": 0
            }
          ]
        },
        {
          "label": "tool_result",
          "color": "var(--agent-log-kind-tool-result-fill)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 2
            },
            {
              "x": "2026-11-19T10:00:10+00:00",
              "y": 0
            }
          ]
        },
        {
          "label": "usage",
          "color": "var(--agent-log-kind-muted-text)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 1
            },
            {
              "x": "2026-11-19T10:00:10+00:00",
              "y": 0
            }
          ]
        },
        {
          "label": "result",
          "color": "var(--agent-log-kind-result-text)",
          "data": [
            {
              "x": "2026-11-19T10:00:00+00:00",
              "y": 1
            },
            {
              "x": "2026-11-19T10:00:10+00:00",
              "y": 1
            }
          ]
        }
      ]
    }
  ]
}
? 0
```
