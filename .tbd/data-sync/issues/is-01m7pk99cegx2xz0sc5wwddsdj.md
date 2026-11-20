---
type: is
id: is-01m7pk99cegx2xz0sc5wwddsdj
title: "One canonical design for open modes: docs/project/architecture/arch-open-modes.md (plain folder, repository folder, mirror; working directory vs revision views; root resolution with guarded walk-up), and bring every drifting plan and guide into line with it (docs only)"
kind: task
status: closed
priority: 1
version: 8
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/558
    at: 2026-11-18T06:18:20.473Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
hold: null
hold_until: null
created_at: 2026-11-18T05:50:12.878Z
updated_at: 2026-11-20T17:00:13.466Z
started_at: 2026-11-18T05:54:45.389Z
closed_at: 2026-11-18T07:55:06.341Z
close_reason: "Merged in #558 (cc7b1b008): docs/project/architecture/arch-open-modes.md, reviews A and B addressed."
resolution: null
duplicate_of: null
---
From the Fable design review of 2026-11-18 (attic/coord/design-review-open-modes.md in the coordinator worktree) and the owner's answers the same day: Q1 any Git repo; Q2 guarded walk-up (+ --exact-root; data modes exact); Q3 Pulls and toggle stay on a revision; Q4 Open URL = mirror, offer the checkout, switch an open window; Q5 View on branch = head as a revision, working-tree copy a separate action; Q6 indicator by the root name, cloud fallback; Q8 a file joins the most specific open folder, never above its repo root; Q9 revisions inert; terminology per Git (working tree / worktree). Implements mb-itzy's 2026-11-07 ask. Blocks mb-8ob8, #546's mode text, mb-m4mg, mb-wup3.

## Notes

2026-11-18: PR #558 (claude/arch-open-modes) adds docs/project/architecture/arch-open-modes.md and brings the documents on main into line. Docs only. Not merged; an independent review follows.
Applied rule: a sentence that is true on main stays and gets a "designed, not built" or "planned in Open Modes" pointer; the review's present-tense wording for unbuilt behavior is listed in the PR body for the pull request that changes the code. The in-flight rows (#546, #539, #540, #552, #534, the chooser) are listed there too and were not touched.
Recommendations awaiting the owner: "working tree" as the term and the chooser's label (not "working directory"); a plain folder and a repository folder show the same folder icon.
Not decided, listed in the document: links that select a branch (mb-itzy); Pulls on a folder served exactly below a repository's root; --remote; a command line for a checkout's revision.
Found: both gaps in "never writes a repository it serves" reproduce on main through a route (commit detail on a blobless clone fetches a pack; a comparison under a cachetextconv driver writes refs/notes/textconv/<driver>). arch-git.md names them. No bead exists for them, for the resolver (walk-up, --exact-root, the root in the Serving line), or for the vocabulary test and shared resolution fixture.
mb-itzy now depends on mb-8ob8, and mb-8ob8's notes cite mb-itzy as its origin.
2026-11-18, review A on #558 (changes requested) addressed at 8ada621fa, fixes in 00f08e5c5; dispositions comment posted on the PR. A1 to A14 fixed, A15 recorded under Not Decided, A16 to A18 done. Terms and Q7 are now Decisions rows; the survey of other tools' terms moved to the PR description. Still open for the owner, in the document's Not Decided: the look of a plain folder beside a repository folder, Pulls on a folder served exactly below a repository's root, whether a --remote server resolves its path, and whether --untrusted is a walk-up guard. The deferred guide wording is in the notes of mb-2wfk and mb-8ob8. Superseded lines above: the terminology is decided, and beads now exist for the resolver (mb-2wfk), the vocabulary test and fixture (mb-ajxe), and the read-only gaps (mb-z849).
2026-11-18, review B on #558 approved; its four Low fixes are in eaf9a1940 and the dispositions comment is posted. B1: the resolver's policy also sets GIT_NO_LAZY_FETCH=1 (a sparse partial clone fetched an ignore file's blob under check-ignore), with a fixture case; mb-2wfk should carry that. No further review round. Not merged.
