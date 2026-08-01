---
type: is
id: is-01kyxrjmmqrya9f3tp76qcnnmv
title: "PR #19 review R4: strengthen wrapped CLI assertion"
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kyxrj3k0zm0d52vvjhnp4zzp
created_at: 2026-08-01T04:16:06.806Z
updated_at: 2026-08-01T04:21:00.763Z
---
R4 Low at tests/test_cli_main.py:412: split assertions lose phrase contiguity because Rich panel glyphs survive unstyle. Normalize panel glyphs in the shared helper and restore one strong assertion.
