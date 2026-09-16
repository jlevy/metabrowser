---
type: is
id: is-01m10vgwqwn8gjdv8fm183vztr
title: "Hosted review Phase 4: PR documents, diffs, and virtual nav collection"
kind: feature
status: open
priority: 1
version: 23
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m0b71xgqp0jgz007h0wtzr3z
  - type: blocks
    target: is-01m10xd6s2fy7qthahs3cz25gk
  - type: blocks
    target: is-01m2h5ar8jct8wbp94xj39gkq4
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m0b71xwkrf39qnq9ccgxmfp4
  - is-01kxry31tw40txkbzctzv1mtsd
  - is-01kxry30twkcz9sg4ecahcg63j
  - is-01m2h7hrjt6yzb16neh8g2zvsd
  - is-01m2h7jjgpzyfbf10238j32z6q
  - is-01m2h9jjh45d8db9rbd0qtscf7
  - is-01m2ktkve5n2fztx8smd6n9vja
  - is-01m2kw2cra83fyszkrptvhfead
  - is-01m2kw2d2arc9hn25pfsc4me50
  - is-01m2kw2dcatp87s48y8ra11jp4
created_at: 2026-08-27T05:36:42.234Z
updated_at: 2026-09-16T01:07:32.361Z
---
Umbrella for incrementally shippable provider-neutral hosted-resource views. mb-xzj3 owns mounted HTTP, mb-6mle owns the generic /hosted address lifecycle, and mb-83w0 owns route-backed ResourceKindSpec plus shared kind/view/model dispatch; together they enable mb-81p5 to register change-request and render a direct cached PR document and File Diff Format comparison without an index. After mb-lnkl and mb-uh6p, mb-iw1v adds the virtual Pull Requests collection, then mb-rldc adds honest file/line/range anchors. Every browser-consumed record is validated; hostile strings stay text or untrusted Markdown; browser and metab resolve the same selection; exact production lifecycle functions run in hosted-review-session and its golden.
