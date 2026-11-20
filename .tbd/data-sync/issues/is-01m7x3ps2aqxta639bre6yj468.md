---
type: is
id: is-01m7x3ps2aqxta639bre6yj468
title: "macOS title folder menu: the check mark of the current entry sits on the name's (first, bold) line, not centred across the two-line row, keeping the accessible checked state"
kind: bug
status: closed
priority: 2
version: 10
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/672
    at: 2026-11-20T22:58:31.644Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-20T18:32:38.727Z
updated_at: 2026-11-20T22:58:31.978Z
started_at: 2026-11-20T18:33:17.490Z
closed_at: 2026-11-20T22:58:31.977Z
close_reason: "PR #672 merged as a1ccf1cc14af75a5bcaa906cf3e7fe3d44d9963c. Main macOS run 44832111266 passed native tests and package checks. The app ZIP embeds the merge SHA, and its checksum and the DMG checksum match GitHub. Automated tests cover the AppKit accessibility mark. The VoiceOver check remains in macOS hand checks step 17 because the local probe lacked accessibility trust."
resolution: null
duplicate_of: null
---
Owner 2026-11-20. Follow-up to mb-z822 (#628), which moved the cloud/folder icon to the name's line but kept the native check centred because a custom onStateImage loses AXMenuItemMarkChar (the accessible checked state). Find a way that puts the check on the first line and keeps the item reported as checked to accessibility (VoiceOver), with a test.

## Notes

PR #672 (claude/menu-check-first-line), head 7572ed26f (was 1b69bd997; the first macOS CI run failed a menu-width test, fixed). No prior notes on this bead, so nothing merged away.

Approach: the chooser's rows are TitleLineMenuItem (Sources/ShellViews): with a subtitle the check is AppKit's own checkmark symbol (13 pt bold small, ink centred at 6.375, 7.5 in a 13 x 16 slot) at the top of an image 2 x RootMark.TitleLineLayout.rise taller, so AppKit centres it on the title's line. Open menu, macOS 26.5.2: check ink centre 0.0 pt from the first title line's (was 7.0 below), 9.0 pt tall, menu width unchanged. The item overrides the legacy accessibilityAttributeValue(_:) so AXMenuItemMarkChar is what a stock item in the same state answers (a custom onStateImage otherwise makes it nil; accessibilitySetOverrideValue changes nothing).

Rejected, all measured on 26.5: NSMenuItem.view (Option alternate never swaps, highlight and tint are the view's to redo); NSMenu.showsStateColumn = false (native check still drawn); title paragraph or baseline tricks (the check is not in the title).

Tests: TitleLineCheckTests (parity with a stock item's mark char for every state and subtitle, directly and through the menu's AX children; the premise that a stock item with the raised check loses it; position, size, column width); four mutations each fail the intended test. ShellViews is now a ShellCoreTests dependency.

Not verified: no AX client (process not accessibility-trusted), so VoiceOver itself is a hand check (qa-macos-app-hand-checks.md step 17); no macOS 15 (package requires 26); screencapture is denied here, so screenshots are the menu window drawn into a bitmap (worktree attic/menu-check-*.png). make -C apps/macos test: all Swift suites pass; its script checks fail one case, the quarantine helper's, because xattr on PATH is a broken pyenv shim on this Mac.


The parent of this bead is:
---
type: is
id: is-01m748xpx7bjg68tfaf3q4nxmj
title: "Native macOS app: thin AppKit shell over metab"
kind: epic
status: open
priority: P1
version: 138
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
child_order_hints:
  - is-01m748xqaqfxbm3rczqhp869bn
  - is-01m748xqrh37ksb7fvh0cqdapm
  - is-01m748xr5tt08pm5p5ykheg1fe
  - is-01m748xrkn32a8mcak4f8yxy4n
  - is-01m748xs18re0g14ge32270n3e
  - is-01m748xsest94amc9cyx26j1zk
  - is-01m748xswj3y4wnc6bfb60kmp6
  - is-01m748xta3y5hxhf6kx1n8psja
  - is-01m748xtr995frd3pgx5zbq2nt
  - is-01m748xv63xk4wtt5nrrr64s2q
  - is-01m748xvkxpj29cp9p8wr6vg5w
  - is-01m748xw1h1hx5p0eakfc0afgr
  - is-01m748xwf9kpmst8t6jk2n95hj
  - is-01m748xwwxrrvvnb49fw9ez5ra
  - is-01m748xxadyc5tfdj366df1ag0
  - is-01m748xxr130p68h0zbjbb6k9f
  - is-01m748xy5zb3zf2d8grsys2b5p
  - is-01m748xykvszgd0b8x0ws7k6j7
  - is-01m748xz1cmg8yrassbyy1jqa5
  - is-01m748xzfj0nvstrsj9766877c
  - is-01m748xzxmaxg55y30n0xybf63
  - is-01m748y0c9k9k6h3zr9pnjgr0f
  - is-01m748y0t19d6e8fjhc0znkbzs
  - is-01m748y18d2xehrzhyh0fjdy38
  - is-01m748y1pa5yyy4wf2t16cpf0y
  - is-01m748y280ktz4beqt4ed9bm3c
  - is-01m744rtrz3b4h8jhz65t8mh1x
  - is-01kxrygx61r5j6rakwqtq7dh74
  - is-01m402f2nzqs37zm1fs3pbjd4t
  - is-01m0m5vwhzn3h5bxyy79w3st82
  - is-01m10vgvh4pvre1adnkgm2egp1
  - is-01m6yk0ja99gwp0vcsh73xaqsn
  - is-01m74231s615a584ej2671j6n9
  - is-01m749191b1q0qr8nrcxp8m986
  - is-01m74919frspvn3y341jcfg5cf
  - is-01m74919x10s489egs2q6hfn22
  - is-01m7491aamdnrexwfg1cp56ke4
  - is-01m75n8tverk8x4ytnfnd3z1m6
… [106 lines omitted]

CI finding: offscreen NSMenu.size of AppKit's own check is not steady (stock menu 143 vs 148 pt across local test processes on 26.5; the 26.7 runner measured 164 vs 165 for the 13 pt slot). A run-time calibration of the slot from it followed the noise, so it was dropped: the slot stays 13 x 16, the width test is one-sided (no wider than stock, to a point) and pins the slot. Unexplained: why the stock check's measured column varies between processes.
