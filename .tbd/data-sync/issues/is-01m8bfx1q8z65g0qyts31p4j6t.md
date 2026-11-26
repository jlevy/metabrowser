---
type: is
id: is-01m8bfx1q8z65g0qyts31p4j6t
title: Survey the ownership rule against real environments and clones
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fw3ppt7qjecxb1m4r276q
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-26T08:35:09.159Z
updated_at: 2026-11-26T08:36:39.876Z
---
Phase 4 prerequisite (plan: Trust and Consent, the ownership rule). The first revision applied the app's ExecutableTrust rule to every source: owned by the user or root, and writable by no group and no other account. The app applies that rule only to a metab the user did not choose, and its own comment says it refuses a standard Homebrew prefix. Survey real layouts before the rule ships for sources: a venv on Homebrew Python, uv-managed Python, pyenv, the system Python; clones and environments under a default umask that leaves a user's own directories group-writable; a clone on a shared volume. Decide how the rule treats group-writable paths (refuse, refuse unless the group is the user's own, or warn), state what the rule does and does not guarantee (it checks entry paths and, after hello, each sys.path entry, not every file below), and keep one implementation, in the home module beside the existing ancestor checks.
