---
type: is
id: is-01m2wc1fbfkfrwpwjejy5vk8g5
title: Below-floor file:// refuse writes home if the directory already exists
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels: []
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-19T08:20:34.286Z
updated_at: 2026-09-19T08:23:46.118Z
started_at: 2026-09-19T08:20:40.355Z
closed_at: 2026-09-19T08:23:46.118Z
close_reason: "Runbook is in docs/qa-v011-repository-library.md; empty-home below-floor refuse no longer writes f01; QA steps executed on #214 tip plus #209 worktree."
resolution: null
duplicate_of: null
---
QA of docs/qa-v011-repository-library.md on ubuntu Git 2.43.0: metab file://$REPO --no-serve correctly refuses with unsupported Git version when METABROWSER_HOME is absent, but if the operator (or mktemp -d) already created that directory empty, acquire_file_source calls open_cache before require_acquisition_git and writes the f01 skeleton (cache/CACHEDIR.TAG, config.yml, locks). Hits must still skip the floor. Do not weaken the floor.
