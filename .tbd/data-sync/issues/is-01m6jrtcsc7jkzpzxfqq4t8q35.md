---
type: is
id: is-01m6jrtcsc7jkzpzxfqq4t8q35
title: Give paged PR file lists a stable identity for each refresh
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhbnan8czw6c97gr5511mr
created_at: 2026-11-04T07:54:16.747Z
updated_at: 2026-11-04T07:54:16.747Z
---
Dedicated correctness review reproduced a PR287 bug with validated backend publications and the production holder: two different same-length REST file lists can share second-resolution fetched_at, reader, listed_from and null base/head. The holder keeps before.js and continues at offset1 while the actual cache contains after.js. Add a stable explicit per-refresh list generation shared by every page, separate from display timestamps, update typed wire/frontend ownership and concise red-green controls for same-second replacement versus same-generation append. Fix in owning PR287 and merge forward; independently review and run required gates/CI. Do not mutate source while normal push session41771 runs.
