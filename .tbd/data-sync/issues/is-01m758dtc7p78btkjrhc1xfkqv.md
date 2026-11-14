---
type: is
id: is-01m758dtc7p78btkjrhc1xfkqv
title: Expose a public KPress API for per-block token maps and rendering
kind: task
status: open
priority: 2
version: 3
labels:
  - kpress
  - upstream
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-11T12:13:21.670Z
updated_at: 2026-11-14T18:47:27.333Z
---
metabrowser.diff.markdown_projection (PR #349, A15) parses each side once with KPress's own MarkdownIt core through three private kpress.format.markdown functions (_markdown_it, _mark_standalone_image_figures, _postprocess_html) under the exact kpress==0.3.5 pin, guarded by tests/test_markdown_diff_projection.py::test_projected_blocks_join_to_kpress_parse_markdown. KPress is first-party: expose block token maps and per-block rendering publicly, then move the projection onto that API and drop the private imports. Review A of #349: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855490584

## Notes

Needs a KPress release after 0.3.5, as mb-jybd does. If mb-a9ek is closed, reparent to mb-2iok.
