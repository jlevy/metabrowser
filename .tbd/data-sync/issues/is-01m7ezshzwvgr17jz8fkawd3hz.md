---
type: is
id: is-01m7ezshzwvgr17jz8fkawd3hz
title: "H112: one surface store — each subject renders into its own kept host, so a return makes no request and shows next frame"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-14-performance-campaigns.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774r8p6ht39jjcf8sj2fejk
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
  - type: blocks
    target: is-01m7d6qy7eb6m07raw2ct53hpg
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-15T06:54:53.434Z
updated_at: 2026-11-15T07:26:41.057Z
---
Architecture review R1 (2026-11-14). Merges H95, H98, H99 (a), H100 and H105, and takes H108's Changes half. Lettered verdicts (a) layout passes per mount 2 → 1, (b) requests before ready on revisits → 0, (c) revisit painted ready ≤ 47 ms (≤ 63 for the 13,000-element source view), (d) Changes and each tab's landing mounted at idle. Needs recorder revision 6 (mb-tpol) and a layout-pass count. Reserved exp-092. Registry row H112.
