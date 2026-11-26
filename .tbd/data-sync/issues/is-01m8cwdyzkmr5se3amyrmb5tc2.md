---
type: is
id: is-01m8cwdyzkmr5se3amyrmb5tc2
title: "test_nothing_in_the_files_panel_moves_from_document_start_to_settled: a 0.00004 shift once in CI"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
created_at: 2026-11-26T21:33:20.755Z
updated_at: 2026-11-26T21:33:20.755Z
---
CI on https://github.com/jlevy/metabrowser/pull/891 at d9463651 (run 45897013864, attempt 1, chrome 1/6): tests/test_files_totals_stable_chrome.py failed one of its 31 cases, 'ignored slow 180px light', with a layout shift of 4.4e-05 at 103 ms whose sources were button#nav-refresh.icon-btn.nav-refresh and div#root-details.root-details. The PR touches no Files panel code; the same test passed 3/3 locally at that head and on the job's one re-run. Find what moves the refresh button and root details by a fraction of a pixel on a slow, narrow pane, rather than loosening the zero-shift bound.
