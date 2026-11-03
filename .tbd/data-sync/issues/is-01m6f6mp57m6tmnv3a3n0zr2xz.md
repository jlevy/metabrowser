---
type: is
id: is-01m6f6mp57m6tmnv3a3n0zr2xz
title: Decide whether to drop copy detection or compute the manifest at fetch time
kind: task
status: closed
priority: 2
version: 2
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3ne8f25m4n06r3d09zw9d
created_at: 2026-11-02T22:38:52.070Z
updated_at: 2026-11-03T00:29:38.552Z
closed_at: 2026-11-03T00:29:38.551Z
close_reason: "Keep -C. Measured on the large-PR performance layer at load 6: dropping it takes the stress manifest from 638 to 206 ms and turns its one copy into an add; the 663-file case goes from 113 to 105 ms with no change in answer. A wrong 'added' costs more than 0.4 s on a rare huge case. A manifest computed at fetch time would remove about 0.7 s of the 997 ms first request, if that is ever wanted."
resolution: null
duplicate_of: null
---
exp-040 item 4: raw manifest takes 37, 71 and 681 ms for no detection, -M50, and -M50 -C on 1,183 files, so -C is about 10x the listing. Dropping it changes what readers see for copied files; a fetch-time manifest interacts with the storage design. About 1 s off a first request. Numbers come back from the fixes agent.
