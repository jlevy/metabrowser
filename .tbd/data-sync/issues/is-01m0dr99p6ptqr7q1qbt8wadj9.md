---
type: is
id: is-01m0dr99p6ptqr7q1qbt8wadj9
title: "Parser ingest completion: GIT binary payloads, REST bare hunks, mbox framing"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-19T19:34:33.413Z
updated_at: 2026-08-19T19:34:33.413Z
---
Research-proven ingest gaps in parse_unified_patch, each a real-world source: (1) GIT binary patch sections (literal/delta, base85+deflate, forward+reverse hunks) are marked binary with content dropped — ingest to inline content refs so binary changes survive the patch path, bounded by size caps; (2) GitHub REST files-endpoint 'patch' strings are bare hunks with no ---/+++ headers — accept with paths supplied out-of-band (filename/previous_filename/status), which the PR plugin (mb-6394) needs; (3) git format-patch mbox framing: From/Subject headers parse fine but the trailing signature ('-- ' + version) degrades the last file to unsupported — strip framing per the format-patch contract (three-dash separator, signature). Each gets hostile-input tests beside the four already pinned.
