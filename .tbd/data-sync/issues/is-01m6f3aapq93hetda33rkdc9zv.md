---
type: is
id: is-01m6f3aapq93hetda33rkdc9zv
title: /pull/<n>/files/<path>
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3dkmagq7az0j52zq4je42
parent_id: is-01m6f39zpnk9rc3kjy552b88qj
hold: null
hold_until: null
created_at: 2026-11-02T21:40:46.933Z
updated_at: 2026-11-03T07:19:03.511Z
started_at: 2026-11-03T06:46:32.451Z
---
The page opens Files changed narrowed to that file, Back and Forward through the page host, no record starts its fetch, --show reports it, and arch-nav-containers.md's Collection panels is corrected.

## Notes

2026-11-03 HANDOFF: done and tested on wip/pulls-4-files (2cd41853, 02dd2d04) except two items. Server and client grammar, the page host's landing, the page's showFile, --show (cli-github-pull-files.tryscript.md), _SHELL_ROUTES, and the URL grammar and arch-map docs are in. A file route with no record mounts the page's usual pending state and the host lands the file once the diff exists. Not done: arch-nav-containers.md's Collection panels still names ChangeRequestIndex; no CHANGELOG line yet. To confirm: the file's address shows Files changed of the whole comparison jumped to that file, not a one-file narrowed document (reasons on mb-q3jt).
