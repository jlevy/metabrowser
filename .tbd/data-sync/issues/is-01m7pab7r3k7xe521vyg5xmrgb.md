---
type: is
id: is-01m7pab7r3k7xe521vyg5xmrgb
title: "View header: move the size, file count and age (e.g. '379.2 MB · 18,344 files · 11m ago') from the upper right to sit next to the file or folder name with a small gap, in the nav bar's style; the upper right is then empty"
kind: task
status: closed
priority: 2
version: 10
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
child_order_hints:
  - is-01m7pdw10jp8vpk7fbw4g994r4
  - is-01m7pjs70jw1s54195e7f84v82
  - is-01m7pkgzth175ysqyfpp41brk9
hold: null
hold_until: null
created_at: 2026-11-18T03:13:59.554Z
updated_at: 2026-11-18T22:04:05.431Z
started_at: 2026-11-18T03:15:32.079Z
closed_at: 2026-11-18T22:04:05.426Z
close_reason: Landed in jlevy/metabrowser#550 (f105941bc)
resolution: null
duplicate_of: null
---
Owner, 2026-11-18 in chat: 'let's remove the file size on the top right of the upper view bar as well and instead put the file age and file size next to the filename with a small gap, trying to fit in with other design styles we already have, much like the nav bar. these numbers 379.2 MB / 18,344 files / 11m ago should all be next to the folder itself. after these changes the upper right will be empty.' Then the upper right holds a small toggle (separate bead).

## Notes

2026-11-18 owner (chat): 'make sure that the headers are better organized for consistency on files, PRs, and commits. All of these should have a similar styling at the top, even if there's some variation. Right now, PRs have icons, and commits and files do not, but files and folders should probably have the corresponding icon: a folder icon for folders and the corresponding file icon that we already use in the nav panel for the files. The font size of the main file name should be the full size, but the enclosing folder and up button (inactive or active) could be more like an eyebrow.' Folded into the same agent's work: one shared header pattern (eyebrow: enclosing folder + up button; title row: kind icon + full-size title + quiet metadata; upper-right GitHub toggle), possibly as a stack.
2026-11-18 owner (chat): 'the overall layout of the header material, the heading, and the metadata below it, and then the tabs for the different formats of the file or the different columns for a PR, should all be similarly styled.' Shared header = eyebrow, heading row, metadata line(s), tab bar; one design-system 'View headers' section; Chrome measurement comparing vertical rhythm across file, folder, PR, commit.
2026-11-18 owner (chat): 'Eyebrow should be optional, but for things like files, it's important to know the enclosing folder, so that's a useful thing.'
2026-11-18 owner (chat): 'Let's aim for consistency. Also, about white versus gray backgrounds and border lines all of this should have a consistent design system.' Grounds and rules for the header block and tab bar become one rule in the View headers section; survey and fix inconsistencies across kinds.
