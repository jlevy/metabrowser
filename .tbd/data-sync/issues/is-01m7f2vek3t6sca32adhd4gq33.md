---
type: is
id: is-01m7f2vek3t6sca32adhd4gq33
title: "Object data model and views: plan and decisions"
kind: epic
status: open
priority: 2
version: 19
spec_path: docs/project/specs/active/plan-2026-11-14-object-data-model-and-views.md
labels: []
dependencies: []
child_order_hints:
  - is-01m7kchtj4fw8xr6cqrjxen0ba
  - is-01m7kchv2nan1dcd9ad4mhwfw8
  - is-01m7kchvk4fztkxw0wfjrdahvr
  - is-01m7kchw2tyf5xxd9vkgqz2py0
  - is-01m7kchwjz8ccxpxq4zy82c4f5
  - is-01m7kchxb9vjmsxz3q6f57fsqa
  - is-01m7kchxxbppkwbbk0egc0r4xm
  - is-01m7kchyd90zv870mp4q856has
  - is-01m7kchyybxgp1syp0g1t968vv
  - is-01m7kchzfvn5kjgn33c5dwxa4k
  - is-01m7kcj00zrdycfj1pfgan5ad8
  - is-01m7kcj0h21ag8mg8jvy5vphd8
  - is-01m7kcj10pdf3kgddaacfs5t38
  - is-01m7kcj1g467xr9syzqj4j4fm6
  - is-01m7kcj1zhedcbge81ch06x6pk
  - is-01m7r76k6f8m2een1fvgt1a1ea
created_at: 2026-11-15T07:48:21.218Z
updated_at: 2026-11-20T17:17:01.550Z
---
Design (not yet implementation) of one object data model with multiple views, a view state agents can read and change, and the Recent tab. Six plan specs, all decisions taken 2026-11-18 (PR #570): the object data model and views (docs/project/specs/active/plan-2026-11-14-object-data-model-and-views.md, Decisions 1 to 23), the view model and view state (VM-1 to VM-10), the Recent tab (RT-1 to RT-7), the agent interface (AI-1 to AI-6; the CLI is the complete agent surface), plugin authoring (PS-1 to PS-7), and the implementation map (Ordering 2: groundwork, then working-tree changes, with the view slice and the /pulls stack in parallel). Implementation lands on separate stacks after #570 merges.

## Notes

2026-11-20 audit: The object model, view model, Recent tab, agent interface, host mode, plugin authoring and implementation map are in plan PR #570 (open, mb-aumr in progress). Host mode's beads are the epic mb-ycjx.
