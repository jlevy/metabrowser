---
type: is
id: is-01m0jsxft0geavafe8qygzj793
title: Goldens for the folder, binary, agent-log, and structured data hooks
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:39:15.775Z
updated_at: 2026-08-30T00:56:27.931Z
closed_at: 2026-08-30T00:56:27.931Z
close_reason: Pinned by cli-api-nav.tryscript.md and cli-api-plugins.tryscript.md via metab --api. Rollup truncation is explicitly out of reach of a sandbox fixture and noted in the golden; mb-crmq's remainder is recorded there.
resolution: null
duplicate_of: null
---
Four kinds get their models from plugin data hooks — folder/*, binary/chunk, agent-log/charts, structured/parsed — and none is reachable outside a browser. The diff hooks are covered by --diff at the model layer but not through the route, so cover diff/document and diff/children here too.
