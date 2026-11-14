---
type: is
id: is-01m7cmptva96jf076a85g0kabx
title: "Storage: cut the per-call ancestor walk cost (getattrlist, batching)"
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-11-14T09:02:41.001Z
updated_at: 2026-11-14T18:44:37.712Z
---
Follow-up from #422 (mb-89zo): after held directory descriptors, the ancestor walk (an lstat plus an ACL read per ancestor, per walk) is most of the remaining private-storage cost: 25,722 of 37,733 GIL-releasing calls in a Pulls session at a 12-deep home.

Options found, none taken: (a) read stat and ACL in one getattrlist(2) call (no new assumption; needs a ctypes parser); (b) batch cached_batch's record and core reads under one private_directory; (c) skip an unchanged ACL read when device, inode, mode, owner and ctime match (every APFS ACL change bumped ctime, but this adds a timestamp reliance to a check that has none, so it needs an explicit security decision). Done when the walk's cost is cut without weakening any guarantee, measured, with a security review.

## Notes

Standalone: a follow-up of the standalone mb-89zo (#422); needs a security review before any option is taken.
