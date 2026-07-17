---
type: is
id: is-01kxj67pty26s2j7bftahawv2a
title: Document compression and archive-format roadmap
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-15T06:08:13.661Z
updated_at: 2026-07-17T21:16:49.698Z
closed_at: 2026-07-15T06:16:17.843Z
close_reason: TODO roadmap is current, public-safe, Flowmark-formatted, and covered by the complete make -j4 verify gate with 669 tests.
---
Create or refresh top-level TODO.md so supported transparent single-file compression formats are explicit and future container/archive support such as tar, tar.gz, tar.zst, and zip is clearly separated and tracked without implying current support.

## Notes

Added top-level TODO.md with an explicit checked-current/unchecked-future split: gzip and zlib supported today; .zst and other single-file formats deferred; ZIP and tar-family archive/container browsing deferred behind navigation and security design. README links the roadmap and architecture names current gzip/zlib support.
