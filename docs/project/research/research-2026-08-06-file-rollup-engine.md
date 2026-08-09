# Research: A High-Performance File Roll-Up Engine (Moved)

**Date:** 2026-08-06 (moved 2026-08-08)

**Status:** Complete — outcome adopted, document moved.

## Outcome

This research asked whether metabrowser should replace its Python walker and inventory
with a native engine, and what that engine should look like.
It surveyed twelve tools across four languages by reading their source (`du`, `ncdu` 1
and 2, `dust`, `dua-cli`, `gdu`, `dut`, `duc`, `fsearch`, `bfs`, `fd`, `scc`, `tokei`),
plus the `notify` and `watchfiles` stack metabrowser runs today.

The answer was yes, as a **standalone project** rather than a subsystem of metabrowser,
because the engine is useful as a CLI and a library independently of this application.

That project is **fdu** — `fd` + `du`, read as “fast du”:

- Repository: <https://github.com/jlevy/fdu>
- Full research document, with the tool survey and the techniques worth adapting:
  `docs/project/research/research-2026-08-06-file-rollup-engine.md` in that repository.
- Implementation plan and current status:
  `docs/project/specs/active/plan-2026-08-08-fdu-phase-1.md` in that repository.

The document moved rather than being copied, so there is one place it can drift from.

## What This Means for Metabrowser

The integration seam is already clean: the walker yields a well-defined record stream,
the inventory consumes it, and plugins consume classification and projections through a
documented API. fdu slots in at the walker/inventory seam without disturbing the plugin
boundary. Replacing that hot path is tracked in the fdu repository as `fdu-p02b`; the
metabrowser-side work will be scheduled here when fdu is ready to be depended on.

What it would remove, all measured in this codebase today:

- The ~7,000 files/s cold walk, so 500k files takes ~70 s.
- `INVENTORY_MAX_FILES = 500_000`, the cap that exists to bound that time and memory.
- The absence of persistence — every server start re-walks everything.
- The ~1.5 s gitignore parse on large roots, and the special-casing it forced (children
  of ignored directories inherit the flag) because per-entry pathspec matching dominated
  walker time at 500k files.

## One Finding That Applies Now

Independent of whether fdu ever ships, the research found a live defect in the current
watch stack.
`watchfiles` maps notify’s event model down to `(change, path)`, and in that
mapping an `EventKind::Other` carrying `Flag::Rescan` falls through to a branch that
discards it. That flag is how inotify’s `Q_OVERFLOW`, FSEvents’ `MustScanSubDirs`, and
Windows buffer overruns all surface — it means “your view is now incomplete, re-walk.”

So after a burst large enough to overflow kernel queues — a `git checkout`, an
`npm install` — the kernel can drop events, notify duly reports it, and the Python layer
never finds out. The inventory silently diverges until restart.

This is not a bug in metabrowser’s code; it is information watchfiles’ simplified API
cannot carry. Tracked as **mb-pn95**.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
