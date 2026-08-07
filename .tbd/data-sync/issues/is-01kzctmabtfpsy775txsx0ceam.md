---
type: is
id: is-01kzctmabtfpsy775txsx0ceam
title: Move the reserved TOC rail into KPress
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-08-07T00:40:35.449Z
updated_at: 2026-08-07T00:40:35.449Z
---
Metabrowser's styles.css carries a "Reserved TOC rail" override: in KPress's wide document band (>=75rem of pane width) the reading column is left-aligned behind a 15rem TOC rail when a TOC exists, but falls back to a centred, measure-capped column when the document has fewer than toc_min_headings headings. The prose then shifts sideways as you move between files.

The host override uncaps both reading-measure caps for the no-TOC case, insets the column by rail + gap, and repeats KPress's wide-band table-bleed reset. That mirrors geometry metabrowser does not own (KPress components.css, "Document layout + Table of Contents").

Durable fix: reserve the rail in KPress itself so both cases share one rule, then drop the host block and its tokens (--embedded-toc-rail-*, --embedded-doc-column-*) plus tests/test_reserved_toc_rail.py on the next KPress bump.
