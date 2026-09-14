---
type: is
id: is-01m2fcq2yxgt7c8pxrb4r915y6
title: "PR #117 review R4: non-UTF-8 git output crashes metab --version"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m2fcq020gq0zzxgs62nrz5rp
created_at: 2026-09-14T07:22:14.876Z
updated_at: 2026-09-14T07:47:47.927Z
closed_at: 2026-09-14T07:47:47.924Z
close_reason: "R4 fixed in da00abc5 (PR #117): surrogateescape decoding, UnicodeError caught; undecodable tag test."
resolution: null
duplicate_of: null
---
src/metabrowser/build_version.py:55-64 decodes strictly; UnicodeDecodeError escapes _git. Use encoding=utf-8, errors=surrogateescape, catch UnicodeError, add a test. PR #117.
