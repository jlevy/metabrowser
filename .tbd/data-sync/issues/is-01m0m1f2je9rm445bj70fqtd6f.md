---
type: is
id: is-01m0m1f2je9rm445bj70fqtd6f
title: "H16: measure against a real repository corpus, not only build_corpus stubs"
kind: task
status: open
priority: 0
version: 2
labels: []
dependencies: []
created_at: 2026-08-22T06:10:26.509Z
updated_at: 2026-08-22T19:00:32.106Z
---
build_corpus's 972 uniformly wide directories of stub files misrepresent at least two hypotheses: /api/catalog is 62 bytes on stubs (vs 4.5 MB claimed at 100k in the plan, H4), and H6's 4,525 ms first row never reproduced. Assemble a corpus from checked-out repositories of comparable size, record its shape in the experiment subject, and re-run the standing baselines. Plan Backlog H16.
