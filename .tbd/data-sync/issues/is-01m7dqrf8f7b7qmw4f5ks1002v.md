---
type: is
id: is-01m7dqrf8f7b7qmw4f5ks1002v
title: "Docs records: retire, move, index, and check 4"
kind: task
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmdjvjrgqd3vpqw3z3zdc
created_at: 2026-11-14T19:15:14.830Z
updated_at: 2026-11-15T05:56:41.732Z
---
Phase 2, PR 8: project records and check 4.

- Retire: delete arch-hosted-review-model.md and arch-external-resources-and-views.md (spec open question 4; the reference/v012-hosted-review-2026-09-30 tag keeps them); move arch-editor-plugin-editing-contract.md to specs/active/ as a draft plan; move arch-vscode-extension-host.md to research/archive/. Add every retired name to the dangling-document-name pattern in devtools/public_hygiene.py.
- Move shipped specs to specs/done/ (their designs were folded in by the layer PRs): open-repo-from-git-url, cli-first-delivery-map, functional-ui-cli-parity, v012-alpha-testing, v012-thin-mirror, pr-watch-and-reconnect, pr-freshness-and-prefetch, scalable-file-search, general-diff-rendering, and the superseded github-provider-and-pull-requests. Confirm github-pulls-tab and pr-review-mirror-and-checkout have no open beads before moving them.
- Move docs/qa-v012-repository-library.md to docs/project/qa/ under a dated name; update inbound links in eleven files.
- Archive superseded research: the file-rollup-engine stub, desktop-app-packaging, web-diff-viewer-architecture, repo-cache-and-git-url-open, file-patch-formats.
- Correct docs/project/README.md: add the seven omitted documents, drop the finished Release Acceptance section, and fix stale descriptions and titles. Refresh the status lines of live specs.
- Add check 4 to tests/test_docs_discipline.py with a failing fixture: the status, footer, and named-check rules also cover docs/architecture.md and the four standards in docs/.
