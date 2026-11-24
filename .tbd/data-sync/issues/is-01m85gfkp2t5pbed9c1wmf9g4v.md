---
type: is
id: is-01m85gfkp2t5pbed9c1wmf9g4v
title: Docs link check parses 8 MB of Markdown (5.3 s CPU) in the module's first test, which passes the suite's 60 s wall budget at load ~450; 101 link targets are parsed twice
kind: bug
status: open
priority: 3
version: 2
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/775
    at: 2026-11-24T00:52:26.838Z
labels: []
dependencies: []
created_at: 2026-11-24T00:49:50.785Z
updated_at: 2026-11-24T00:52:26.853Z
---
tests/test_docs_discipline.py::test_relative_links_resolve was stopped by the suite timeout at load ~450 while markdown-it parsed. Measured 2026-11-23 on a 10-core M1 Pro (attic probe docs_links_cost.py): 271 authored files, 8.0 MB; the check costs 4.9-5.3 s CPU (setup 0.7 s, teardown 1.3 s more when run alone, the server import of the autouse cache resets). Parsing is linear, 0.25-0.78 us/byte with the largest file (design-system.md, 450 KB) no dearer per byte than small ones: nothing super-linear. Redundant: _Tree.links and _Tree.anchors each parse, so the 101 files a link names a heading of are parsed twice, about 1 s of the 5 s; parsing every file once costs 3.1 s and rendering+hardening all 271 1.35 s, so computing anchors for every file at link time would save almost nothing, and only a pre-scan of which files are fragment targets would cut the re-parse. CI's call is 8.7 s. Locally the call took 42-46 s at load ~380-400 and the whole item 56-58 s.
