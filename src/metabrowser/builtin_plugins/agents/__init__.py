"""The ``agents`` plugin: coding-agent logs, and operational visibility into agent homes.

The plugin owns the JSONL log adapters and the Log, Charts, and Raw JSON views of an
agent log (:mod:`.adapters`, :mod:`.sidekick`, the manifest's JavaScript and CSS), and
the provider layer for Claude Code and Codex homes: the shared model (:mod:`.model`),
the event kinds and mapping tables (:mod:`.kinds`), and one provider per agent
(:mod:`.claude`, :mod:`.codex`).
The manifest's ``[plugin] register`` names :mod:`.adapters`, so plugin discovery imports
it, which registers the adapters. Every module reaches Metabrowser only through
``metabrowser.plugin_api``.
See ``docs/project/specs/active/plan-2026-11-19-agent-operations-views.md``.
"""
