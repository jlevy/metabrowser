---
type: is
id: is-01m0nc7rq3354n302fzswaszty
title: Remote agent sessions ship a toolchain older than the repo requires
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-22T18:37:55.811Z
updated_at: 2026-08-22T18:37:55.811Z
---
A Claude Code remote session starts with uv 0.8.17 and Node 22.22.2 / npm 10.9.7. The repository requires uv >= 0.11.26 (uv.toml required-version) and Node 24.18.0 with npm >= 11.10 (.node-version, .npmrc min-release-age).

The failure is confusing rather than clear. `make install` exports UV_EXCLUDE_NEWER='14 days', and a uv that does not understand a relative duration reports it as a malformed date:

    error: invalid value '14 days' for '--exclude-newer <EXCLUDE_NEWER>': `14 days` could not be parsed as a valid date

That reads like a bad Makefile value, not an old uv, and uv never gets far enough to enforce its own required-version. npm fails separately on the min-release-age key.

The repository already solves this shape of problem for one tool: .claude/scripts/ensure-gh-cli.sh installs a checksum-pinned gh from SessionStart. The same pattern would fit here, installing the CI-pinned uv (0.11.26, sha256 6426a73c3837e6e2483ee344cbc00f36394d179afcba6183cb77437e67db4af0, the checksum ci.yml already pins) and Node 24.18.0 verified against nodejs.org SHASUMS256.txt.

Verified in this session: with those two versions installed, `make verify` passes end to end with no repository change.

Consider also having uv.toml's required-version failure surface before the exclude-newer parse, so an old uv says which uv it needs.
