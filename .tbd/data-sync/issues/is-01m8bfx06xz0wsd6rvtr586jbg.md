---
type: is
id: is-01m8bfx06xz0wsd6rvtr586jbg
title: Hook response headers from an inventory of built-in hooks
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-26T08:35:07.613Z
updated_at: 2026-11-26T08:35:07.613Z
---
Phase 0 (plan: Hook Response Headers), split from mb-3q4e. An inventory test collects every response header a built-in data hook sets and every request header one reads, and fails when the policy would drop one: on main that includes Content-Encoding on the diff hook's stored gzip body (builtin_plugins/diff/sidekick.py), accept-encoding, and x-metabrowser-verified on the pull-request hooks. Policy: pass content headers (type, encoding, disposition, language, range, accept-ranges), caching headers, server-timing, x-metabrowser-*, and every restricting header; refuse set-cookie, access-control-*, and location; add nosniff to every hook response and Content-Security-Policy: sandbox; default-src 'none' to an HTML, SVG, or XML response with no policy of its own. Two steps: worker hooks get the full allowlist with the worker in Phase 1; applying the refusals and the default policy to in-process hooks, built-ins included, is this bead, with a changelog fragment, because it can change what an existing plugin's HTML does. SECURITY.md and the threat model gain the rule.
