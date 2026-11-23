---
type: is
id: is-01m836qya23kghgk2m3t9em8nc
title: "Address review A on #722 (rollup layer)"
kind: task
status: closed
priority: 2
version: 10
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
child_order_hints:
  - is-01m83ccpbn5hy106mqq6g5xj5c
  - is-01m83cczqe40xbmma1vh3v102t
  - is-01m83cd9zc3vte359rgjd3jcpz
  - is-01m83cdje93r95wg5vgdxcfr04
  - is-01m83cdt49bjjcj8afcc8j9faw
  - is-01m83ce1ntnt27qc8eyxpwqyz7
  - is-01m83ce87ftr08zgrmtaazgbpw
hold: null
hold_until: null
created_at: 2026-11-23T03:21:09.184Z
updated_at: 2026-11-23T05:31:23.751Z
started_at: 2026-11-23T03:22:01.557Z
closed_at: 2026-11-23T05:31:23.746Z
close_reason: every finding of review A has a disposition, posted on the PR at the pushed head
resolution: null
duplicate_of: null
---
Review https://github.com/jlevy/metabrowser/pull/722#pullrequestreview-6016192666. A1 Medium: merged alone, heaviest-first spends depth-3 budget on undrawn level 3 (nestDepth 2 at this layer) -> state that #722 merges only in the stack merge with #723. A2 Medium: the test passes under path order ('deep' < 'wide'); rename the heavy branch and add ignored-vs-unignored, bytes-vs-files, and exact-tie cases. A3 Low: key the heap on (-weight, level, path, seq) so an all-zero tree expands level by level. A4 Low: wire_models.py:233-235 and server.py:3267-3269 docstrings: children null also means not reached by the node budget. A5 suggestion: _ordered_children sorts every child; record the depth-12 cost beside ROLLUP_MAX_DEPTH or select with heapq.nsmallest. A6 suggestion: per-child priority.
