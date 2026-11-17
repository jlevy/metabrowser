---
type: is
id: is-01m7ktyd6twx956pr9ch7zngk5
title: "PR #496 review A1: the serial marker also takes a test off three interpreters before merge"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7ktycr1m7798eaqhyky3qnr
created_at: 2026-11-17T04:06:21.657Z
updated_at: 2026-11-17T04:06:21.657Z
---
docs/project/specs/active/plan-2026-11-16-fast-ci.md:112-116, :171, :178-192, :527, :557-560 at 1e6f437f. serial meant both 'needs the machine to itself' and 'checked on one interpreter before merge'; a test marked serial for xdist reasons, and test_process_group.py's 17 non-Chrome tests, lose 3.12, 3.14, 3.14t before merge. Decision: split the marker; only chrome_profile tests go to one interpreter.
