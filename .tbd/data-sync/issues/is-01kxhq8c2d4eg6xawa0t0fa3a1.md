---
type: is
id: is-01kxhq8c2d4eg6xawa0t0fa3a1
title: "PR #1 review A3: bound and chunk gzip text reads"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:26.764Z
updated_at: 2026-07-15T01:46:26.764Z
---
Review A3 and inline thread (Medium). src/metabrowser/server.py and gz_io.py: honor offset/limit and cap decompression without trusting gzip ISIZE.
