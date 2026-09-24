---
type: is
id: is-01m3am6pfnqs97wb8pzk5kwzn5
title: Pull-request header says 'wants to merge' for merged and closed PRs; skipped checks counted as neutral
kind: bug
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-24T21:12:36.084Z
updated_at: 2026-09-24T21:15:52.713Z
---
Found during the v0.12 alpha acceptance (mb-gnr9) on the integrated stack (PR #241; installed wheel 0.11.1.dev400+250a10c4), on cli/cli#14128 (merged; head 5dfc6b06b53e8c3962b28d3ebf00e9b696daf985).

1. The pull-request header says "<author> wants to merge into <base> from <head>" for every state. For a merged pull request the page shows the Merged badge next to "<author> wants to merge into trunk from <head branch>". `paintHeader` in `src/metabrowser/builtin_plugins/github/pull-page.js` writes the phrase unconditionally. GitHub says "merged N commits into" for a merged pull request, and a closed one should not say "wants to" either.
2. The Checks summary reads "13 success · 13 neutral" when the record's 26 check runs are 13 `success` and 13 `skipped`, so skipped runs are counted as neutral. The individual rows do say "skipped".

Reproduction: `metab https://github.com/cli/cli/pull/14128 --no-open --port <p>` with a signed-in gh, then open `/pull/14128` (the conversation tab).

Acceptance test: in `tests/dom/github-pull-page-session.js` and its golden (`tests/golden/cli-ui-github-pull-page.tryscript.md`), the header model for a merged, a closed-unmerged, and an open pull request uses state-appropriate wording, and a record with skipped check runs is summarized with a `skipped` count distinct from `neutral`.

Owning PR: #233 (PR view).
