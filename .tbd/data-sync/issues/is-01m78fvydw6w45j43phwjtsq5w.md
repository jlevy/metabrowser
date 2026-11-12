---
type: is
id: is-01m78fvydw6w45j43phwjtsq5w
title: Plugin SDK package and worker protocol, with the host's worker client
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvywxsmc0m4481ypk3zbq
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:07.899Z
updated_at: 2026-11-12T18:21:08.379Z
---
Phase 1 (plan: The Plugin SDK, The Worker Protocol, Process Model). New uv workspace member metabrowser-plugin-sdk (import metabrowser_plugin_sdk), stdlib-only, Python >=3.12: the inventory identity codec moved from inventory_engine.contract and ArtifactPath moved from gz_io (the host imports both from the SDK), path helpers and root callbacks bound to the session, the content reader calling the host from a worker, LogEvent and register_log_parser, host services, HookRequest/HookResponse (Starlette responses accepted by duck typing; streaming refused), and the worker module (python -I -m metabrowser_plugin_sdk.worker). Protocol v1: JSON header line plus body_len bytes, ids for multiplexing, both directions; hello with major version and capabilities (fail fast on a major mismatch), list, check, call, cancel, parse, root_changed, shutdown. Host client in plugin_loader: spawn in the server's process group with the stdin lifeline, stdout redirection in the worker, stderr to the server log, deadlines, cancel on disconnect, body and header bounds, restart with a crash limit, idle exit. Golden protocol session and fault tests (exit mid-call, hang, garbage frames, stdout prints, oversized body, major mismatch, stdin EOF). Add the worker protocol row (VERSION + CAPABILITIES) to the Standing Compatibility Answers.
