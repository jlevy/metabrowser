---
type: is
id: is-01m36k3xm77y33seww2jbwwb69
title: "URL open: HTTPS mirror, GitHub URL resolver, ref/path split, seamless refresh, browser serving"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m36k3y0t6fvtqhskx3cqxx95
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-23T07:36:38.789Z
updated_at: 2026-09-23T07:36:39.193Z
---
Implements the URL-open row (old 2A+2C): credential-free HTTPS clone and fetch; internal Host interface with github.com resolver (repo, tree, blob with line anchors, commit, pull target retained, raw.githubusercontent.com); refuse other github.com shapes; ref/path split against local refs longest first; missing ref triggers one fetch; stale-while-revalidate refresh (about one minute) with one in-flight fetch per mirror; serve a pinned GitRevisionSubject in the browser and CLI; forced untrusted profile on URL-opened roots (mb-99ub); served /raw relative references (mb-g5je); stall bound measurement (mb-rati); SIGHUP handling (mb-163x). Hermetic local smart-HTTP fixture plus opt-in live smoke. Independent review, make verify, green CI.
