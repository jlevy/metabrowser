---
type: is
id: is-01m774q0ep0jq6vhb790rart0v
title: "Epic: instant transitions and stable layout for the native app"
kind: epic
status: open
priority: 1
version: 38
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
child_order_hints:
  - is-01m774qvqk729advxcgh6e13g4
  - is-01m774qx0e5bprjjzsmatmbe77
  - is-01m774qxq0w386b8ap8fq2nyyx
  - is-01m774qyepwq8bhzn81kc1bz6r
  - is-01m774qzdxvfrwsyzmx5dgtce1
  - is-01m774r1q8f0z91jm14wd3m2h6
  - is-01m774r3cs24qrntm810jeqndz
  - is-01m774r4psqf6bqd00a8pae0dw
  - is-01m774r5n7h5t75ydr0b6m5z00
  - is-01m774r6nmb6sxnp5gbpy1sfaz
  - is-01m774r7k4mqvs813sjppzvceh
  - is-01m774r833ppra9j905zvb5z6a
  - is-01m774r8p6ht39jjcf8sj2fejk
  - is-01m774r967jvcvcx4btkpyfzeg
  - is-01m774r9n7z8bymhs94yjq67sw
  - is-01m774ra6cpn1h8jnk2mkzq0nh
  - is-01m774ramhp4w2e08j3t30aw9g
  - is-01m774rb30k3bd8ehwy6exbwq4
  - is-01m774rbhb56bd9d69fq1y3f0c
  - is-01m774rbz6q8kxewh1pxe06xv4
  - is-01m774rcdp9y54xga8fmgy2912
  - is-01m774rcw2wb289avpff6qvm1e
  - is-01m774rdb8j84szr2bamkxphvm
  - is-01m774rdstn0r4rtfnn10sdbp9
  - is-01m774re9ewc3k6c8hp5x78376
  - is-01m774rerk521sprp8ys3ana0t
  - is-01m774rf6smnw3sw8c2rw322px
  - is-01m774rfn15h0t9ys9eg0nvgyx
  - is-01m77616mh9yfzy5cq7daccafn
  - is-01m77979r1cfhmvawew2mfb84r
  - is-01m77bbymqdmjexeq490ev38hs
  - is-01m77ewnf0w3ey51q6wewvyg50
created_at: 2026-11-12T05:46:57.364Z
updated_at: 2026-11-12T09:22:29.684Z
---
Implement the ranked improvements in docs/project/research/research-2026-11-11-ui-apparent-performance.md. Every item is a measured performance-loop round (hypothesis in the load-time plan, exp record, verdict) and closes on its verdict. Ends with a campaign summary covering every item, in Chrome and WKWebView.

## Notes

Operating map (2026-11-11). Corpus: /Users/levy/wrk/github/metabrowser-perf-corpus, detached worktree at 7a02fed4 (frozen). Control build: /Users/levy/wrk/github/metabrowser-perf-control at origin/main 09903292 (.venv/bin/metab). Lanes, each a worktree from origin/main 09903292 with its own node_modules and .venv: research docs claude/ui-perf-research (PR #364: research doc, plan, H86-H105 registry, audit); harness claude/perf-transition-scenario at metabrowser-perf-harness (mb-4z4u, exp-058 baseline, ports 8890-8899); delivery claude/perf-delivery at metabrowser-perf-delivery (mb-3m3l, mb-pdul, mb-rldd, ports 8880-8889); caches claude/perf-caches at metabrowser-perf-caches (mb-8a8g, mb-mbd3, ports 8900-8909); layout claude/perf-layout at metabrowser-perf-layout (mb-n3r5, then mb-4z69 and mb-6chh after the audit mb-eo0s, ports 8910-8919). Research server for audits: port 8872 (8871 belongs to another session). PRs target main without stacks (github-stacked-prs not granted) and merge in order after review and green CI; the owner approved merging once review is complete. Native shell items (mb-w4kd, mb-25nv) stay unmerged with apps/macos. Push with --no-verify after focused checks while the machine is loaded; CI is the full gate. Added 2026-11-11: PR-page lane claude/perf-prpage at metabrowser-perf-prpage (mb-6chh, mb-gsa0, ports 8920-8929); layout lane keeps mb-n3r5 and mb-4z69. Audit mb-eo0s closed into the research doc at 81b4d2b1. Owner authorization for this campaign (verbatim, 2026-11-11): 'Make sure we complete this work and complete end-to-end review processes following tbd guidelines. Once everything is done, this can be merged.' 'Map out all this work as beads under an epic so you don't lose track of anything, and implement everything on it. You can operate autonomously to do this.' 'Be sure we check the performance measurements and follow our standard performance iteration process for all of this, and give final updates on the performance for everything.' Recorded policy at origin/main 09903292: github-editing and github-workflows unanswered, github-merge confirm-every; the owner's words above authorize reviews, fixes, and merges for this campaign's PRs. Auto-fix enable for #368 was denied by the app's classifier. Update 2026-11-12: #364 merged (9fad3080). origin/main 02db045a (#371) records github-editing granted; github-merge stays confirm-every, so merges rest on the owner's campaign authorization above. Harness v2 frozen at metabrowser-perf-harness-v2 (b9da543b); #373 under senior review; WebKit probe mb-fevz on claude/perf-wkprobe (metabrowser-perf-wkprobe). Rounds running: caches (v1), layout and PR page (v2); delivery waits for a quieter machine. Update: #373 review A found a Blocker (painted-ready unbounded by later DOM work) and four Highs; rounds run on harness v1/v2 are pilots only (counts usable, timings not). Addressing pass re-records exp-058 on the fixed harness and a new independent corpus clone /Users/levy/wrk/github/metabrowser-perf-corpus-v2 (7a02fed4, own refs). All lane rounds re-run on the fixed copy. Caches pilot commit 87f2f30b preserved in reflog and attic/pilot-87f2f30b; caches lane also fixing a large-render INP cost (16 to 96 ms on design-system.md revisit).
