---
type: is
id: is-01kzctmabtfpsy775txsx0ceam
title: Move the reserved TOC rail into KPress
kind: task
status: closed
priority: 3
version: 3
labels: []
dependencies: []
created_at: 2026-08-07T00:40:35.449Z
updated_at: 2026-08-09T17:43:39.290Z
closed_at: 2026-08-09T17:43:39.289Z
close_reason: 'Done in b44cbd5: kpress==0.3.1 pinned, kpress_adapter.py passes toc_rail="reserved", the host Reserved TOC rail block and its four tokens deleted, tests/test_reserved_toc_rail.py removed, and the dependency contract now pins the opt-in. Verified in Chromium: with-TOC and no-TOC documents both land at 368-1136px, 48rem measure.'
---
Metabrowser's styles.css carries a "Reserved TOC rail" override: in KPress's wide document band (>=75rem of pane width) the reading column is left-aligned behind a 15rem TOC rail when a TOC exists, but falls back to a centred, measure-capped column when the document has fewer than toc_min_headings headings. Measured in Chromium at a 1300px pane, the prose also runs 43rem instead of 48rem.

UPSTREAM FIX IS READY: kpress branch fix/reserve-toc-rail (kpr-d30j) adds RenderOptions.toc_rail / KPressRenderRequest.toc_rail / format.toc_rail, default "auto" (byte-identical renders), opt-in "reserved". Awaiting a KPress patch release.

On the KPress bump, in ONE change:
1. Delete the "Reserved TOC rail" block from src/metabrowser/static/styles.css and the four --embedded-toc-rail-* / --embedded-doc-column-* tokens on :root.
2. Pass toc_rail="reserved" on the KPressRenderRequest built in src/metabrowser/kpress_adapter.py.
3. Delete tests/test_reserved_toc_rail.py.

Do NOT keep both: upstream reserves the rail by gridding the band and placing the prose in track 2, the host override does it with a left margin, and together they double the offset. tests/test_reserved_toc_rail.py::test_the_host_override_is_dropped_once_kpress_reserves_the_rail_itself fails on the bump to force this.
