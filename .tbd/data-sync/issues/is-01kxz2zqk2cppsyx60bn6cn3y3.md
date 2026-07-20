---
type: is
id: is-01kxz2zqk2cppsyx60bn6cn3y3
title: "P1: folder envelope in api_file and folder kind registration"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies:
  - type: blocks
    target: is-01kxz2ztvzj0tj8pp088rpmvp3
  - type: blocks
    target: is-01kxz2zv6jz6e5w02acj1xb44d
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T06:21:34.177Z
updated_at: 2026-07-20T06:22:30.279Z
---
server.py: split the is_file guard in _api_file_impl; add _api_folder_envelope(subpath, target) returning {type/kind folder, views, dir aggregates from inventory.get, readme_path, no-store}; add _find_dir_readme and refactor _initial_file_path onto it. file_kinds.py: add 'folder': [] to VIEW_REGISTRY. Tests: tests/test_api_folder_envelope.py (envelope shape, README detection incl. case variants, pending aggregates, traversal 404s, no-store header). See spec 'Server: Folder Envelope'.
