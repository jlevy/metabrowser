---
type: is
id: is-01m87qe40b2dtvmc1b0y9czszy
title: "Guided review: the pager shows the arrow it should hide on the overview and the last step"
kind: bug
status: closed
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/795
    at: 2026-11-24T21:37:59.244Z
labels: []
dependencies: []
parent_id: is-01m87ky2a36j5yg4pf9827xxd6
created_at: 2026-11-24T21:29:50.858Z
updated_at: 2026-11-24T22:13:05.980Z
closed_at: 2026-11-24T22:13:05.980Z
close_reason: "Fixed in #795"
resolution: null
duplicate_of: null
---
styles.css: .github-pull-guide-pager .btn {display:inline-flex} comes after .github-pull-guided-review [hidden]{display:none} at the same specificity, so a hidden pager arrow still shows (visible on the overview in #795's pull-10 screenshots). Found while building #795.
