---
type: is
id: is-01kzsb4jnyd56wy89xmztkmz2m
title: "Repo cache: extend git/process.py and add repo_clone.py (reuse the existing runner)"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
created_at: 2026-08-11T21:19:58.653Z
updated_at: 2026-08-16T08:05:43.419Z
extensions:
  linear:
    id: 0ffb0ef8-e09f-4e96-8736-01e0592ab450
    linked_at: 2026-08-16T08:05:43.419Z
---
Reuse metabrowser.git.process rather than adding a second path to the git executable; it already provides fixed argv, timeouts, capped reads, child reaping, GIT_* scrubbing, and a typed GitError hierarchy.

Add to process.py: version detection (absent today, needed for the 2.49 backfill gate); stdin=DEVNULL on spawn (currently inherits the parent's); SSH_ASKPASS_REQUIRE=never, GCM_INTERACTIVE=never, and GIT_SSH_COMMAND BatchMode.

New repo_clone.py: hardened clone (core.symlinks=false, hooksPath empty, protocol.allow=never + https/ssh, no submodules, --filter=blob:none, -- before URL, fsckObjects left default) and backfill over run_git with clone-scale timeouts, since GIT_SUBPROCESS_TIMEOUT_S=15 bounds request reads and is far too short for a clone. Plus stderr classification into actionable CLI messages.

Lives outside metabrowser.git so that package's stated read-only contract stays true.
