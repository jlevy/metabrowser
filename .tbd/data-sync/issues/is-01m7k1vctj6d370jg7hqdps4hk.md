---
type: is
id: is-01m7k1vctj6d370jg7hqdps4hk
title: Design the macOS app's publishing setup (signing, notarization, DMG, install checks) to a current best-practice standard, adapting a sibling Electron app's proven setup
kind: task
status: in_progress
priority: 1
version: 11
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
child_order_hints:
  - is-01m7k2w8wrwrypxm2vxyqaaa8v
  - is-01m7k2wy21hnkyp3p2sssrjfty
  - is-01m7k2wyj6vv09snsk781hpvsz
  - is-01m7k2wz25n92m141a2c6rzj3m
  - is-01m7k2wzxnnfkzcr7eg8ngptcq
  - is-01m7k2x14rvw39nm958bfcwv67
  - is-01m7k2xcrjxtgfe2mepxas1434
  - is-01m7k2xdgr9b8sra4vrd372fe2
  - is-01m7k2xe5286604ke24q8svdgq
hold: null
hold_until: null
created_at: 2026-11-16T20:47:48.560Z
updated_at: 2026-11-16T21:06:24.033Z
started_at: 2026-11-16T20:49:22.082Z
---
Owner, 2026-11-16: look at the developer setup of a sibling private Electron app and its GitHub repo, design what metabrowser's Apple app publishing needs to be equivalent, including its testing tools that check app signing and that the app downloads and sets up correctly; adapt what makes sense, follow current best practices, and bring them up to date (that repo is over a year old). The sibling repo is private: metabrowser's public docs describe adopted practices without naming it or copying from it. Deliverable: a plan spec PR.
