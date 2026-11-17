# QA: Files Totals Layout, 2026-11-16

**Date:** 2026-11-16

**Status:** A dated record of the measurements behind the Files totals’ layout rule
([Navigation Metadata Line](../../design-system.md#navigation-metadata-line), “The Files
totals”), taken for `mb-h3hc` and its two review rounds on pull request #490.
`tests/test_files_totals_stable_chrome.py` holds the rule on every change.

## The Report

The owner, 2026-11-16: the “+ N ignored” line of the Files panel appeared later than the
rest, so the view shifted, and “this should never happen.
if something is slow it should be laid out in a stable way with a progress box to show
it is filling in”.

## Method

Headless Chrome 152 at 1280 by 900, with the navigation pane at its default 300 px and
at its 180 px minimum, in both themes.
A probe installed at the document’s start recorded, every animation frame, the boxes of
the filter bar, each metadata line, and the first rows, and every layout shift without
input. Slow loads held the server’s tally (`/api/tree?depth=0`) 2 or 3 s at the page.
A shell drawn before the walk finished the root was simulated by removing the inlined
totals from the served page; a mid-walk tally by rewriting the first one as
`tally_cache_status: "scanning"` with nothing ignored, and holding the event stream that
brings the root’s entry 1.5 s after it.
From 2026-11-17 the first case also holds the event stream until first paint, because
its snapshot carries the same totals in the root’s entry.
Without that hold the snapshot filled the line 17 to 100 ms after first paint for the
folder with nothing ignored, and in one CI run it arrived before first paint, so no
frame recorded the held line, although nothing moved.

## Results

Before, on `main` at `102da3655`, on this repository (1,772 tracked files and 7,898
ignored):

| Load | What moved |
| --- | --- |
| 300 px, tally at once | The band grew from 37 to 56.5 px at 858 ms, when the split arrived and its ignored half wrapped; the rows moved down 19.5 px; layout shift 0.00264 |
| 300 px, dark | The same, at 629 ms |
| 300 px, tally held 3 s | The same, at 3,658 ms |

On the check’s fixtures, `main` moved the band and the rows 39 px at 180 px, where the
split wrapped to three lines, and 19.5 px at 300 px for a folder whose tracked count
reads “1,201 files (45.8 MB)”.

The first fix (`b0fd48a`) inlined the root’s totals and gave the ignored count its own
line. Review A found two moves left on a shell drawn mid-walk, measured with that head’s
browser code: a provisional tally with nothing ignored took the held line away and the
root’s entry brought it back (held, none, counted: 19.5 px, layout shift 0.00078), and a
folder with nothing ignored lost its held line (19.5 px).
The reducer that review asked for (`createRootTotals`) never takes a provisional tally,
and keeps a drawn line as “No ignored files”.

After, at the head that closed review B: every load of the check, a folder with ignored
files, one with none, and the wide one; the tally at once and held; 300 and 180 px; both
themes; with the shell’s totals removed; and with a provisional first tally, moved 0 px
with no layout shift after first paint.
The one shift before first paint is the filter bar wrapping as it is filled at 180 px,
`mb-a5pa`.

## Startup Cost

The reducer and the markup ride in `navigation.js` and `app.js`, which the shell loads
before its first tree.
`devtools.check_startup_scripts` measured the shell at 224,720 bytes before the tracked
line’s rule, 1,071 under its budget, and the rule added about 120 bytes.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
