---
type: is
id: is-01kzsb4jnyd56wy89xmztkmz2m
title: "Repo cache: git_cmd wrapper (version detect, non-interactive env, hardened clone, backfill, stderr classification)"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
created_at: 2026-08-11T21:19:58.653Z
updated_at: 2026-08-11T21:20:08.225Z
---
Narrow wrapper over the git executable. Anchored version parse tolerating Apple/Windows/untagged suffixes; non-interactive env (GIT_TERMINAL_PROMPT=0, askpass neutralized, SSH_ASKPASS_REQUIRE=never, GCM_INTERACTIVE=never, BatchMode, stdin=DEVNULL, wall-clock timeout) inherited not rebuilt; hardening via -c flags only (core.symlinks=false, hooksPath empty, fetch.recurseSubmodules=false, protocol.allow=never + https/ssh, gc.auto=0); transfer.fsckObjects left at default. Classify stderr into the four actionable cases.
