---
type: is
id: is-01m0t8mn4jqd56cchdhvzkjz10
title: Make folder discovery symlink test portable on case-insensitive filesystems
kind: bug
status: closed
priority: 2
version: 3
labels:
  - testing
dependencies: []
created_at: 2026-08-24T16:11:15.985Z
updated_at: 2026-08-24T16:29:56.138Z
closed_at: 2026-08-24T16:29:56.136Z
close_reason: Split README discovery, canonical-precedence, and symlink-rejection coverage into portable tests; focused and full suites now report zero skips.
resolution: null
duplicate_of: null
---
The test that combines canonical README preference with symlink rejection creates README.md and Readme.md in one directory. Default macOS filesystems treat those as the same path, raising FileExistsError; the broad OSError handler misreports that as symlinks unavailable and skips coverage. Split the independent behaviors into portable fixtures and ensure the focused suite has no skips.
