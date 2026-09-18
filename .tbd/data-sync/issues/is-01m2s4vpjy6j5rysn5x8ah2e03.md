---
type: is
id: is-01m2s4vpjy6j5rysn5x8ah2e03
title: Stage a file:// fetch into a worktree-free store (no publication)
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-18T02:17:21.758Z
updated_at: 2026-09-18T02:17:26.303Z
started_at: 2026-09-18T02:17:26.303Z
---
Claim a staging entry, ls-remote the credential-free file:// source, init --bare --template=, write the store config, and fetch with --filter=blob:none. Detect filter ignored vs honored from received objects, not stderr. Record the configuration snapshot digest and validate the observed HEAD and object format. Leave results in staging only: no repository-stores rename, no source alias, no serving, no --no-serve. Abandon deletes the staging entry. file:// must pack, not git clone --local hardlinks.
