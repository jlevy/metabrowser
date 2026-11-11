---
type: is
id: is-01m76c75t4s8acbw8earxzt4q9
title: "PR #352 B2: App-driven reinstall and removal can mutate an install another owner's server uses"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76c6vcvp3rkctrfv1ykv9qz
hold: null
hold_until: null
created_at: 2026-11-11T22:38:52.739Z
updated_at: 2026-11-11T22:41:10.562Z
started_at: 2026-11-11T22:38:58.889Z
closed_at: 2026-11-11T22:41:10.561Z
close_reason: "fixed in 5136540f: app-driven Reinstall, Remove, and upgrade change nothing while the registry lists another live server on that install; the app names each with its owner, asks the user to stop it, rechecks, and never signals it; claim 5, summary, repair bullet, and plan Phase 5 (mb-895s, mb-34oi) match; unlisted processes such as metab --api recorded as a remaining gap. Confirmed by the same checks and a re-read."
resolution: null
duplicate_of: null
---
Medium. PR #352 review B (https://github.com/jlevy/metabrowser/pull/352#pullrequestreview-5866200355); follows A4 (mb-y4if). docs/project/research/research-2026-11-11-uv-and-macos-app-install.md:377 stops app-owned servers but only names other live servers before Reinstall or Remove proceeds; Flow 2 makes an ordinary CLI install, so a terminal-owned server can be running from it (request-time import at src/metabrowser/builtin_plugins/github/sidekick.py:246, static mount at src/metabrowser/server.py:4251). Fix: defer the mutation until no known non-owned server uses the install; ask owners to stop, recheck, never signal; carry into Phase 5 (mb-34oi, mb-895s).
