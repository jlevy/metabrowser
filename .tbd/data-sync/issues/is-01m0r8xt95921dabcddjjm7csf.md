---
type: is
id: is-01m0r8xt95921dabcddjjm7csf
title: Implement and evaluate the fdu inventory provider
kind: feature
status: open
priority: 1
version: 35
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
child_order_hints:
  - is-01m0tc6jhy1c64c4z6m3z2xxtq
  - is-01m0tgwqjj6w5awgwbgqtk1mqe
  - is-01m0txhaybmj82ym2wcm85zz0b
  - is-01m0tytbmjsb46bnmh5134r5tg
  - is-01m7kp7j7g54v20azrhzrss82w
  - is-01m7kp7jjzwzxk91zzc8bwtbj4
  - is-01m7kp7jy30bn8dbgp2rb2q4qn
  - is-01m7kp7k8sq30h8fsrw6x5c0gc
  - is-01m7kp7kkvd7mqey9qswckbk82
  - is-01m7kp7kywbn845wb69cy1aca0
  - is-01m7kp7macfgf1hykxf2vy49ma
  - is-01m7kp7mn0pb2xvh3cwa7akam7
  - is-01m7kp7n0ew0br72a5f20rdpah
  - is-01m7kp7nba9sw577y4k2cesvbb
  - is-01m7kp7nppf4swardrp6c2gj8y
  - is-01m7kp7p1np55ak0r9cz02fsex
  - is-01m7kp7pdbd237kbtma6kv9p0x
  - is-01m7kp7przq129yanbjfmr6kpm
  - is-01m7kp7q43wpwgn8qatzgvqjwr
  - is-01m7kp7qf40tbnx48zc2myjcbr
  - is-01m7kp7qstpnem1zdnvznm2veb
  - is-01m7kp7r5gs472n9g927516cpk
  - is-01m7kp7rgntx2bzfsp2836gyw9
  - is-01m7kp7rwg98164mggx64spn2j
  - is-01m7kp7s7mp21yntm16hx21cv6
  - is-01m7kp7sjq0vq764bt925h5bx3
  - is-01m7kp7sy55e31vh95940sr8cx
  - is-01m7kp7t8wdy5ng1warp2dn5yh
  - is-01m7kp7tkg5gpjb3vy3e2g6b42
  - is-01m7kp8pp3yx6b4xcad1da0y1n
  - is-01m7krf558hqc66yc8d6qabedg
  - is-01m7m17dpsrh1qmdx50e08xkzn
  - is-01m7m2w3gwk2bvqnvhjezdkt06
created_at: 2026-08-23T21:37:47.300Z
updated_at: 2026-11-17T06:24:54.812Z
---
Phase 2 of the inventory-provider implementation plan. Prove the real PyO3 seam, implement the fdu Rust library behind the same InventoryHandle contract without mirror state, run the shared parity and reliability suites, measure Python versus fdu at the engine/server/browser layers, and add automatic selection only if the adoption gates pass.

## Notes

Final PR101 review establishes native adoption gates: native aggregate projections without rebuilding a Python inventory graph, recovery/session policy (mb-6o0l), useful pinned-page completion and explicit eviction under churn (contract now states semantics; current Python behavior fixed in mb-6elt), text/stream walk semantics (mb-iyu7), and measured binding/readback costs (mb-l2eh). The Python stack can merge separately after full verification.
