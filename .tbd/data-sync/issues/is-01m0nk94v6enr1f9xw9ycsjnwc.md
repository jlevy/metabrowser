---
type: is
id: is-01m0nk94v6enr1f9xw9ycsjnwc
title: Squeezed file-header address cuts the filename and hides the copy control
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T20:41:01.029Z
updated_at: 2026-08-22T20:41:10.315Z
closed_at: 2026-08-22T20:41:10.314Z
close_reason: "Fixed on claude/release-readiness-review-idotjj: weighted shrink with per-part ellipsis, verified by re-measuring the same widths in a real browser. Tests pin the shrink ordering."
---
Found in the browser check mb-hqth and mb-l6qg were handed over for. The address the file header gained renders correctly at ordinary widths; below a certain pane width it fails in two ways at once, neither of them visible from the rendered HTML.

`.file-header-path` is a flex row with `overflow: hidden`. Only `.file-header-root` could shrink; every `.folder-crumb` and separator was `flex: 0 0 auto`, by an explicit rule ("Crumbs keep their size; only the dimmed root prefix above gives way"). That is the right order while the root still has width. Once it reaches zero the run has no give left, so it overflows the clip.

MEASURED, on a 296px header -- a 620px window at the default nav width -- showing `/Users/.../worktrees/<name> / src / metabrowser / color_oklch.py`:

    header  root   filename cut   copy control outside the box
    460px   95px   0              0
    380px   15px   0              0
    360px    0     0              5px
    320px    0     19px           45px
    300px    0     39px           65px

Below a 375px header the root is exhausted. From 360px the copy control is pushed outside the clipped box, where it can be neither seen nor clicked. From 320px the filename itself is cut -- and cut against the parent's clip rather than by its own text-overflow, so there is no ellipsis and no sign that anything is missing.

FIX. Weighted shrink instead of no shrink: the root outshrinks a directory, a directory outshrinks the current segment, and the separators and leading slash stay fixed. Every shrinking part carries its own ellipsis. Re-measured across the same widths: nothing is cut and the copy control stays inside the box at every width down to 240px, while the filename holds 92% of its width where the directory has given up 36% of its own.

Crumbs also gained a title, since a narrow pane now ellipsizes them and the hover is the only place the whole component is legible.

Pinned by `test_address_gives_way_from_the_root_end_and_never_cuts_a_segment`, which asserts the ordering between the shrink weights rather than their values.
