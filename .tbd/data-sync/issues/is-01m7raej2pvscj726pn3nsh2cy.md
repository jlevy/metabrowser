---
type: is
id: is-01m7raej2pvscj726pn3nsh2cy
title: "Page: explain GitHub sign-in and scope failures from the status route"
kind: feature
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-18T21:54:17.285Z
updated_at: 2026-11-18T21:54:17.285Z
---
Follow-up to mb-si2g. The plan's Sign-In section says the page, the app, and goldens read the same states through one route, but it does not say concretely what the page shows, so mb-si2g left the page alone. The route exists: POST /api/plugin/github/status (body {} or {"fresh": true}), which returns {host, state, message, fix, gh_path, gh_version, account, token_source, scopes}. builtin_plugins/github/gh_status.py has the state table. Today the Pulls tab and the pull-request page explain a failed refresh from its PullDataState alone. A token without the repo scope appears there only as not_found_or_private, with a scope hint appended to the message when the server's kept status says missing_scope. To do: decide with the owner where the page shows the account and the fix (for example, in the failure notes of the Pulls tab and the pull page for not_logged_in, gh_missing, gh_too_old, and not_found_or_private), and whether Fetch/Retry should send fresh:true first. Follow the parity rules: a node session plus a cli-ui golden, and a functional aspect row whose data input is /api/plugin/github/status.
