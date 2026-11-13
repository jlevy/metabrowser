---
type: is
id: is-01m7a06m31dqw1wrxx9yewqnxp
title: "Diff plugin: load the git path codec at its stamped /static address (review E1 of #372)"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-13T08:25:49.408Z
updated_at: 2026-11-13T08:25:49.408Z
---
Review E of #372, E1 (Low, optional, deferred). The issue is on main too, so #372 did not
introduce it.

`src/metabrowser/builtin_plugins/diff/index.js:263` loads the git path codec with
`await import("/static/git-path.js")` when `window.MetabrowserGitPath` is missing, which
happens on a page that did not get it as a pinned-revision startup script
(`PIN_STARTUP_SCRIPTS` in server.py). Since #372, the shell names `/static` files at
`/static/<file>?v=<digest>` and serves them `immutable` only at that address. The bare
URL is revalidated on every new load, so this one import costs a conditional request
where the shell's own copy of the file costs none.

A fix has to give the plugin the stamped address rather than spell the path. For
example, the shell could publish it the way it publishes the asset bundles, or the
plugin could load the codec through the SDK's asset loader. A test should pin that the
import names the current stamp.

Not trivial, and not contained in #372: the plugin cannot compute the digest, so the fix
needs a new shell-to-plugin contract (see the internal-contracts rule in AGENTS.md).
