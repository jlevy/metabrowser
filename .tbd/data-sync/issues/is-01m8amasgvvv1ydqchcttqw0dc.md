---
type: is
id: is-01m8amasgvvv1ydqchcttqw0dc
title: "PDF preview golden fails under devtools.run_goldens on macOS: C.UTF-8 locale makes BSD sed reject PDF bytes"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-26T00:33:19.386Z
updated_at: 2026-11-26T00:33:19.386Z
---
tests/golden/cli-api-pdf-preview.tryscript.md fails under devtools.run_goldens on macOS since 3e7eda713: Python's PEP 538 locale coercion puts LC_CTYPE=C.UTF-8 in the child environment, and BSD sed -i rejects the PDF's non-UTF-8 bytes ('illegal byte sequence'). Passes via tryscript directly and on Linux CI. Fix by construction: run the golden's sed with LC_ALL=C, or replace sed on binary files with a byte-safe tool.
