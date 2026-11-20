- Current Claude Code session transcripts open as agent logs with the Log and Charts
  views. Since about Claude Code 2.1.247 a transcript’s first `assistant` record comes
  after line 20, so these logs opened as plain JSONL. Queue operations, attachments, and
  session metadata records each show as one compact line.

- Codex rollout files (`~/.codex/sessions/**/rollout-*.jsonl`) open as agent logs
  through a new `codex-rollout` adapter.
  The Log shows the conversation, the commands, file changes, and MCP calls run inside
  Codex’s `exec` tool, per-response token usage, and each turn’s duration.
  The `codex exec --json` stream, which the `codex` adapter already parsed, now opens as
  an agent log too. Compressed rollouts (`.jsonl.zst`) and rollouts older than the typed
  envelope do not open yet.
