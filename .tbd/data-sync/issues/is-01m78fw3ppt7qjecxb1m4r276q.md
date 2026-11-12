---
type: is
id: is-01m78fw3ppt7qjecxb1m4r276q
title: Repository discovery and per-clone decisions with named providers
kind: task
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78gmwnk00rz776w8w8k7g9j
  - type: blocks
    target: is-01m78fw226k1aejzey9xamd4e7
  - type: blocks
    target: is-01m78fwdh6mt5frdg94thadjkh
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:13.301Z
updated_at: 2026-11-12T21:17:44.938Z
---
Phase 3 (plan: Repository Plugins; Key Decisions 2, 3, 4). Discovery for folder servers only: the clone from its own reader (nearest .git no higher than home, ownership-checked, common directory read so linked worktrees resolve to their clone; not the GitHub-only repository context); the environment from the clone's primary worktree (uv project or workspace root's .venv, a top-level .venv, or [tool.metabrowser.plugins] environment); providers read as data from dist-info entry_points.txt, workspace members' pyproject.toml, and .metabrowser/plugins/*/manifest.toml, shown with version and install location, never labeled own or library. Undecided discovery runs after first paint, bounded (2,000 distributions, 64 directories), names escaped, uncached. Decisions: undecided (report only, serve nothing), trusted (clone path and identity = device:inode of the Git common directory; normalized origin for display only; approved providers; further folders), denied. A new provider asks; version bumps do not; a reclone at the same path is undecided again; linked worktrees share the decision and run the primary environment's code unless opted in for one command. Trust writes: terminal answer or the app's --expect SHA256; no --yes. Missing providers reported with 'set up the environment as the repository documents'; no command guessed. Never for Git sources, pins, mirrors, --untrusted, or the cache home; never from a revision a pull-request page shows. Built-in names forbidden to repository sources. Update SECURITY.md and docs/plugins.md in the same pull request. Deferred: content-bound and parent-folder decisions. Supersedes mb-m1mw.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
