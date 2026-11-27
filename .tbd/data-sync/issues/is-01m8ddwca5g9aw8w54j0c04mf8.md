---
type: is
id: is-01m8ddwca5g9aw8w54j0c04mf8
title: Check what a Markdown link to a folder without its closing slash opens on a served folder
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-link-preview-tooltips.md
labels: []
dependencies: []
parent_id: is-01m8cte9rj7s82c4ywp7n3ph3z
created_at: 2026-11-27T02:38:18.948Z
updated_at: 2026-11-27T02:38:18.948Z
---
Found while fixing review I1 on https://github.com/jlevy/metabrowser/pull/912: on a served folder, /api/file answers a folder path given without a closing slash (as [docs](docs) spells it) with a 404, 'Could not open this folder', while the link's card says 'Opens here in Metabrowser'. Check whether the in-app navigation the resolver hands the link (static/repository-links.js) opens the folder anyway; if it does not, the resolver or the route should treat a path that names a folder as the folder, as git_revision_file already does on a pin.
