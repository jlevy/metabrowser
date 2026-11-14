---
type: is
id: is-01m7d6qz1nstxweev0yg5488rb
title: Attribute exp-079's unaccounted wrong-way results to the changes that cause them
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-14T14:17:52.437Z
updated_at: 2026-11-14T14:32:59.960Z
---
exp-079 left H86 (b), H87, H88 (a) and H106 unresolved at final main on wrong-way results their own records do not account for: H86 (b)'s four pr_header_ms cells and nine painted-ready cells (the PR first-paint holds, which exp-059 does not account for); H88 (a)'s and H106's main_subject.commits_to_pulls painted ready 79.4 to 112.1 ms, cause unknown, since exp-080 measured it unchanged with the hold in place; H87's 17 on landing and files (static and KPress requests 41 to 44 and 18 to 19, preview_top_replaced 3 to 4, data_network, frames to ready; exp-064 put the KPress rise down to H91 (a)'s face loading); H88 (a)'s commits.cold.1. Each record's deciding metric is met. A round that measures each lane's merge against the one before it would say which change each result belongs to.
