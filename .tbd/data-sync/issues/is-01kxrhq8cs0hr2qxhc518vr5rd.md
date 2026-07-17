---
type: is
id: is-01kxrhq8cs0hr2qxhc518vr5rd
title: Review Node and npm development requirements
kind: task
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-17T17:24:24.088Z
updated_at: 2026-07-17T17:28:27.499Z
closed_at: 2026-07-17T17:28:27.499Z
close_reason: "Completed in e4df7ac: preserved the owner's README voice, documented runtime and contributor prerequisites, retained the shared Node 24.18/npm 11.10 floor, scoped Markdown spacing fixes to the KPress host, regenerated the neutral-path screenshot after a settled render, added regression coverage, passed make verify with 705 tests, and passed GitHub Actions run 29600115127."
---
Confirm the Node/npm engine floor against the actual JavaScript tooling, current LTS support, and KPress; document which prerequisites are runtime-only versus contributor-only in the README.

## Notes

Kept Node >=24.18 <25 and npm >=11.10 <12: Node 24 is the current LTS line, npm 11.10 introduced min-release-age, lower Node support would require a separately upgraded npm and new CI coverage, and KPress uses the same floor. README now states Node/npm are development-only; normal runtime requires Python 3.12+ and uv.
