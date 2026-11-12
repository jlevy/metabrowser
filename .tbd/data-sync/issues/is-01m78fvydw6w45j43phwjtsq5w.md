---
type: is
id: is-01m78fvydw6w45j43phwjtsq5w
title: Plugin runtime injected as metabrowser, and the worker client
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvywxsmc0m4481ypk3zbq
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:07.899Z
updated_at: 2026-11-12T21:17:38.475Z
---
Phase 1 (plan: The Plugin Runtime, Process Model, Hook Response Headers; Key Decision 1). A stdlib-only runtime package inside the wheel, put first on each worker's sys.path and importable as metabrowser, so documented plugin imports resolve to the host's code whatever the environment holds (the second spike ran all three downstream plugins unchanged this way). It holds the identity codec (moved out of inventory_engine.contract), ArtifactPath with gz_io and content_errors, the path helpers and root callbacks, the content reader with a per-call host handle table, LogEvent, register_log_adapter, detect_adapter with built-in detectors separated from prettyfmt, JsonlParseLimitError, CLIError, host services, HookRequest/HookResponse, and the worker loop: every name plugin_api and metabrowser.__all__ export for sidekicks. Worker client: posix_spawn of <interpreter> -I -B in the server's process group; request pipe on fd 3 and reply pipe on fd 4, close-on-exec in the worker; fd 0 /dev/null, fd 1 stderr to the server log; SIGINT ignored; request-pipe EOF lifeline; allowlisted environment plus manifest-declared names; multiplexed frames both ways; deadlines that kill the worker after a grace and fail its in-flight calls; restart with a crash limit; idle exit except with open streams; stop on environment change, restart on next call when manifests are unchanged. Header policy: pass content headers and every restrictive header (CSP, nosniff, referrer, frame, permissions, cross-origin policies), refuse set-cookie, access-control-*, location, and unlisted; host adds nosniff, and a sandbox CSP to HTML, SVG, or XML lacking one, for in-process hooks too; request headers accept, content-type, if-none-match, if-modified-since, x-metabrowser-pin; handler time in the existing Server-Timing. Golden protocol session and fault tests per the plan's Testing Strategy.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
