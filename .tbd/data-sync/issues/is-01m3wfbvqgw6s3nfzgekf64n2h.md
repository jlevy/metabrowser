---
type: is
id: is-01m3wfbvqgw6s3nfzgekf64n2h
title: A mirrored repository shows a commit hash as its folder name and hides where it is stored
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T19:34:22.189Z
updated_at: 2026-10-02T00:39:22.764Z
started_at: 2026-10-01T19:34:25.682Z
closed_at: 2026-10-02T00:39:22.755Z
close_reason: "PR #263: a mirrored repository shows its name in the main heading, nav header, tree root and tab title, with the short commit beside the ref and a copy control for the full commit; the heading shows 'mirror in <location>' (the bare store directory, with ~) and a tooltip saying it is a bare repository with no checked-out files. One display location in /api/source/status and the heading; a file:// origin under the home is shown with ~; every other route, header and error still names no cache path (sweep widened; five leak mutations fail it). Regular folders: three null fields added to /api/source/status, +82 bytes of app.js, tooltip geometry identical to base. Independent review: P1 tooltip regression and three P2s fixed; 76 of 76 mutations killed; CI green. Decision recorded in the thin-mirror plan."
resolution: null
duplicate_of: null
---
Reported by the user 2026-10-01 after opening https://github.com/jlevy/squares with the stack tip: the main view's breadcrumb root is the full 40-hex commit ('fe6399451f1c01635c12c9aa5c176822da5dbc42 / README.md'), and nothing on the page says where the repository is stored. The user's decision, in their words: 'the name of the folder in the main view nav and titles should not be an inscrutable hash just because we opened up the folder from a github url. the apparent folder should be the name of the repo, as it would be if it was checked out. and it should be visible where that folder actually resides, it should not be hidden, it should be in our .metabrowser cache directory. this could be via tooltips at least, and perhaps a better indicator using ~/.metabrowser etc on the main heading on the page view, as we do with other regular folders'.

What to build. (1) Name: wherever a served mirror or pin shows its root as a name (breadcrumb root, nav header, tree root, browser tab title, the Serving banner), show the repository's name as a checkout would have it: the last path segment of the origin without '.git' ('squares' for https://github.com/jlevy/squares; the same rule for any https:// or file:// origin). The commit stays visible but secondary: the short commit beside the ref, as the nav header already shows ('main fe6399451f1c'), and the full commit available by tooltip and copy. Escape the name with the existing display helpers; an origin is untrusted. (2) Location: show where the mirror is stored, as regular folders show their path, with the home directory as '~' (the shared tilde helper): at least a tooltip on the heading, and a visible location in the main heading or its line. Be honest about what the directory is: the cache holds a bare Git mirror and the page reads files from Git objects at the pinned commit, so there is no checked-out folder; the directory to name is the source's directory under the cache (cache/sources/<slug>, which carries the repository name), and the text should say it is a mirror of <origin> at <commit>. Decide whether to name the source directory or the store directory, and say why.

This changes an existing rule on purpose. The stack keeps cache and store paths out of every HTTP route and JSON envelope, and tests pin it (the no-leak tests in tests/test_cache_routes.py and the Git content route tests; QA runbook 5.1 says 'No cache path in the output' and fails on a METABROWSER_HOME path). The user's decision is that the location is shown. Make the change narrow and deliberate: one display field, tilde-abbreviated when under the home directory (absolute otherwise, as for regular folders), carried by one route or model that the shell reads; every other route still names no store path, and file content, error messages and --api data envelopes other than that field stay path-free. Check the reason the rule existed (a served mirror is forced untrusted) and confirm that untrusted content still cannot read the field: repository Markdown renders inert with no scripts, and /raw is an opaque-origin sandbox. State the new rule in the architecture doc and update the tests that pinned the old one, rather than deleting them.

Parity (AGENTS.md): the display name and location are data, so they belong to a route or model reachable through 'metab --api' or '--show' with a golden; the heading and tooltip get a browserless session and golden; only paint may be exempt.

Spec: record the decision in docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md (Decisions, dated 2026-10-01, by the user) and correct the passages that say a served page never shows a cache path.
