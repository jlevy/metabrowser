---
type: is
id: is-01m78fw3ppt7qjecxb1m4r276q
title: Repository discovery and per-clone decisions bound to a token, an environment, and providers
kind: task
status: open
priority: 1
version: 14
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m78gmwnk00rz776w8w8k7g9j
  - type: blocks
    target: is-01m78fwdh6mt5frdg94thadjkh
  - type: blocks
    target: is-01m8bfx1aaxf7qyzn1n2h1ap4v
  - type: blocks
    target: is-01m8bfx231spr2pvhzetq1j5as
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:13.301Z
updated_at: 2026-11-26T08:37:20.286Z
started_at: 2026-11-26T08:35:34.385Z
---
Phase 4 (plan: Repository Plugins; Key Decisions 2, 3, 4). Discovery for folder servers only, and again when a server's subject changes: the clone from discovery's own reader (nearest .git no higher than home; a .git file makes the folder a clone's worktree only when the common directory's worktrees/<name>/gitdir names it back, since one hand-written .git file makes Git report any clone's common directory, reproduced); the environment from the clone's primary worktree (uv project or workspace root's .venv, a top-level .venv, or what [tool.metabrowser.plugins] environment there proposes); providers read as data from dist-info entry_points.txt with direct_url.json, workspace members' pyproject.toml, and .metabrowser/plugins/*/manifest.toml in the primary worktree. The repository's own settings can only propose. Undecided discovery runs in serve mode only, after first paint, with bounds set from a measurement, names escaped, uncached. Decisions: undecided (report only, serve nothing), trusted, denied. A trusted decision binds the clone's path and a 128-bit token Metabrowser writes under <common directory>/metabrowser/clone-token (a device and inode are reused: on ext4 a different repository cloned at the same path kept both in 5 of 5 rounds), the environment's prefix, and each provider's name and install origin. A new provider, a changed origin, or a moved environment asks; a version bump from the approved origin does not; a reclone is undecided; listed worktrees share the decision and run the primary environment's code unless opted in for one command. A bare repository has no primary worktree, so the trust mode asks which worktree holds the environment. Trust writes: metab ROOT --plugins-trust with a terminal answer, or the app's --expect SHA256 over the path, environment, authority, and each provider's name, version, origin, and declared authority; no --yes. Missing providers reported with 'set up the environment as the repository documents'; no command guessed. Never for Git sources, pins, mirrors, --untrusted, or the cache home. Built-in names forbidden to repository sources. Update SECURITY.md, arch-threat-model.md (the plan's Threats table), docs/working-with-agents.md, and docs/plugins.md in the same pull request. The authority a decision grants is mb-p62c; the ownership rule's group question is mb-5qw0. Supersedes mb-m1mw.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
