- Coding-agent log support is now the built-in `agents` plugin, in place of `agent-log`:
  its JSONL adapters (Claude Code, Codex, Pi, Gemini) and the Log, Charts, and Raw JSON
  views live there. The charts hook moves from `/api/plugin/agent-log/charts` to
  `/api/plugin/agents/charts`; kind and view ids are unchanged.
  A JSONL file no adapter recognizes now reports the adapter `unknown`, where it
  reported `claude`. The agent adapters register when plugins are discovered, so a
  script that calls `detect_adapter` without starting the server gets `unknown` for
  them.
- Plugin authors: a manifest’s optional `[plugin] register = "dotted.module"` names a
  Python module that discovery imports once for registrations such as
  `register_log_adapter`. It applies to built-in and installed entry-point plugins; an
  operator-directory plugin is JavaScript-only, so the field is ignored there with a
  warning and reported by `metab --doctor`.
