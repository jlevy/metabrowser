---
type: is
id: is-01m85j15gxgp9najr7tq33jtxw
title: Pin the legend rail's trailing 0.7rem TOC inset (PR 776 review A1)
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-24T01:16:54.676Z
updated_at: 2026-11-24T01:16:54.676Z
---
Review A1 (Medium) on https://github.com/jlevy/metabrowser/pull/776#pullrequestreview-6032161064 at head ae638cb82. overview.css:228 copies KPress's .kpress-toc padding (components.css:482, 0.5rem 0.7rem 1rem 1.2rem) as padding-inline: 1.2rem 0.7rem, but nothing pins the trailing 0.7rem: in a scratch clone, padding-inline: 1.2rem 0 passes tests/test_overview_readme_toc_chrome.py. The copied KPress literal also has no fast contract pin, unlike the entry insets in tests/test_kpress_dependency_contract.py::test_pinned_kpress_owns_the_toc_insets. Fix: (1) in tests/dom/overview-readme-toc-chrome.mjs EDGES, require each legend percent's right edge to equal the first TOC entry's right edge in the wide band (both 1360.06 at 1920 px); (2) in test_kpress_dependency_contract.py assert _kpress_values(components, '.kpress-toc', 'padding') == ['0.5rem 0.7rem 1rem 1.2rem'] and that the overview.css rail rule's padding-inline is '1.2rem 0.7rem'. Owning bead of the PR: mb-6pwk.
