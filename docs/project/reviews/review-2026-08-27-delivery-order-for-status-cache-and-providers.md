# Review: Delivery Order for Git Status, the Repository Cache, and Providers

**Date:** 2026-08-27

**Author:** Metabrowser maintainers

**Status:** Complete.
Findings are open; no plan has been revised in response yet.

**Scope:** The architecture and planned design at `3d04a78`, reviewed against a stated
delivery order:

1. Git status working cleanly in the Git tab;
2. pointing Metabrowser at a GitHub URL and having it work from the repository cache;
   and
3. cached GitHub data and pull-request browsing.

Read: the
[Git-status plan](../specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md),
the
[repository-library plan](../specs/active/plan-2026-08-11-open-repo-from-git-url.md),
[Git and comparison sources](../architecture/arch-git-and-comparison-sources.md), the
[HTML trust plan](../specs/active/plan-2026-08-06-html-rendering-and-trust-model.md),
and the bead graph for all four.

## Verdict

**The architecture supports this order; the plans do not yet describe it.**

The layering is sound and needs no change: priority 1 adds a comparison source, priority
2 adds an acquisition path beneath it, priority 3 adds a provider above it.
Nothing in the order inverts a dependency, and the choice to do status first is better
than it looks — see [What the order gets right](#what-the-order-gets-right).

But three of the findings below change what the order *costs*, and two of them are
invisible from the plans that were prioritized.
Priority 2 in particular cannot ship as described without work that lives in a fourth
plan nobody named, and it promises a URL shape the plan explicitly rejects.
Resolve R1 and R2 before committing to a sequence.

## What the order gets right

Worth stating, because it was not obvious and it constrains everything after it.

**Status before cache is the correct dependency order, not just a preference.** Cache
integrity calls the status service’s `is_clean` predicate, so that the definition of a
clean tree cannot drift between two porcelain parsers.
`mb-ew38` depends on `mb-u4mf` in the bead graph for exactly this reason.
Had the cache been prioritized first, that dependency would have forced either a second
parser or an unchecked cache — the two outcomes both plans exist to prevent.
The stated order gets this for free.

**The layers stay in order.** File Diff Format knows nothing about Git; Git produces it
through the `DiffSource` port; providers reference Git object ids and never replace the
object store. Priorities 1 through 3 move strictly up that stack.
A pull-request view in priority 3 resolves provider refs to object ids and reuses the
entire shipped pipeline, so it is a new acquisition path rather than a new renderer.

**Priority 1’s known blocker is already cleared.** The virtualized history window read a
scroll offset it did not own, which would have been inherited and amplified by a Changes
section above History.
That is fixed, and the Changes/History header structure is decided.

## Findings

### R1 — Blocker: priority 2’s critical path runs through a plan that was not prioritized

`mb-ew38` (*generic URL open and offline reuse*) is blocked by `mb-vib1` (*capability
set, `--untrusted` profile, and client publication*), which is blocked by `mb-cun0`
(*sandbox `/raw` responses and require same-origin proof on `/api`*). Both blockers are
open `P1` tasks belonging to
[the HTML rendering and content-trust plan](../specs/active/plan-2026-08-06-html-rendering-and-trust-model.md)
— 632 lines, `Status: Draft`, nothing implemented.

This is not a footnote.
A fetched repository is third-party content, so serving one means having the untrusted
capability profile first, and that profile rests on a same-origin and sandboxing change
to routes that already ship.
Priority 2 therefore contains an entire security workstream that its own plan mentions
only as a gate.

The consequence is an estimate that is wrong rather than merely optimistic: whatever
priority 2 is thought to cost, add two unscoped `P1` security tasks and the design
review of a Draft plan.

**Fix (pick one):**

1. Admit the trust work into priority 2’s scope and sequence it explicitly — `mb-cun0` →
   `mb-vib1` → `mb-ew38` — accepting that the first user-visible result arrives later
   than the cache work alone would suggest.
2. Define a narrower priority 2 that does not serve fetched content: acquisition,
   identity, publication, and CLI inspection only, with serving gated behind the trust
   work as a separate deliverable.
   This ships the cache machinery early and honestly, but the thing a user would
   actually notice still waits.

Option 1 is the honest reading of the stated goal.
Option 2 is only worth taking if the cache internals need to be de-risked before the
trust work is affordable.

### R2 — High: “any GitHub URL” is a promise the plan does not make

Phase 1B accepts repository-root clone URLs: `https://host/path/to/repository`, the same
with `.git`, `ssh://`, and the SCP-like form.
It explicitly leaves tree, blob, commit, issue, and pull-request URLs unsupported until
a provider phase can resolve them unambiguously.

The URL a person actually has in their clipboard is the one from a browser address bar:

```text
https://github.com/pallets/flask/blob/main/src/flask/app.py
https://github.com/pallets/flask/tree/main/src
https://github.com/pallets/flask/pull/5123
```

Under the current plan the first two are rejected, which reads as the feature being
broken rather than bounded — the repository is right there in the path.
“Point Metabrowser at a GitHub URL and it just works” fails on its most common input.

**Fix:** add web-URL normalization to Phase 1B, before the provider phases.
Reducing `/tree/<ref>/<path>` and `/blob/<ref>/<path>` to a repository root is pure
string work on a shape GitHub has kept stable for a decade; it needs no API, no
credential, and no provider record, so it does not violate the provider-neutral
boundary.
Carrying the trailing `<ref>` and `<path>` through as an initial selection is a
natural follow-on and can be deferred.
Pull-request and issue URLs stay out of scope — those genuinely need a provider — but
they should fail with a message naming the repository URL that would work.

### R3 — High: priority 3 depends on a phase absent from the priority list

The dependency map gives Phase 5 (*GitHub acquisition*) two prerequisites: “2
job/storage primitives, 4 schemas”.
Phase 4 is in the stated priority 3. **Phase 2 is not in any stated priority**, and
neither is Phase 3 (the chooser).

So priority 3 either silently includes Phase 2 — generic catalog, refresh, repair,
purge, job progress, cancellation, size accounting — or it depends on primitives that
will not exist. Neither is currently visible to whoever schedules it.

**Fix:** name the specific primitives Phase 5 needs.
If it is the job lifecycle (progress, cancellation, stage outcomes) and the atomic
storage publication, those are a small extraction that priority 3 can carry itself, and
Phase 2’s catalog and purge surface can stay unscheduled.
If it genuinely needs the catalog, insert Phase 2 into the priority list rather than
discovering it during Phase 5.

### R4 — Medium: a format project stands between the stated goal and priority 2

Phase 1A must land before Phase 1B: the application-home resolver, `config.yml`,
`cache/layout.yml`, format history, a future-format failure path, a sequential migration
harness, SoftSchema adoption as a new runtime dependency with its supply-chain
exemption, packaged deterministic compiled schemas, compile-drift and corpus-validation
and schema-inventory and installed-wheel checks, atomic YAML, application-home locking,
quarantine, recoverable trash, `CACHEDIR.TAG`, and a startup reclamation sweep.

The plan’s justification is sound and should not be dismissed: a cache is released data
from its first write, and retrofitting migration under entries that already exist costs
more than building it first.
The concern is not that the work is wrong; it is that priority 2’s first visible result
now sits behind a schema and migration project whose size is nowhere estimated.

**Fix:** size Phase 1A explicitly and decide deliberately, rather than discovering it
mid-build. If it is large relative to appetite, the trim candidates are the ones that
only pay off when a *second* reader exists — the migration harness, the format-history
machinery, and arguably compiled-schema drift checking.
Identity, atomic publication, locking, and honest state are not optional; they are what
makes an interrupted clone safe.

### R5 — Medium: priority 1’s evidence gates are not schedulable

Git-status Phase 1 has three measurement gates whose outcomes become implementation
constants: the submodule inspection policy, the entry/byte/timeout/debounce/row budgets,
and whether copy detection is worth its cost.
All three sit inside `mb-u4mf` alongside the implementation.

Measurement that shares a bead with the code it constrains tends to be done to justify
the code rather than to choose it, and its result is never separately reviewed.
The plan also states that if a complete `--untracked-files=all` status cannot be bounded
usefully, the phase returns to design review — which is a real possibility that cannot
surface if the gate is invisible.

**Fix:** split the dirty-tree corpus and the measurement run into their own bead ahead
of `mb-u4mf`, with the recorded numbers as its deliverable.
The backend bead then starts from chosen constants instead of producing them.

### R6 — Medium: nothing sequences these three against the in-flight P0 work

`tbd ready` currently surfaces eight open `P0` items, all in the end-to-end load-time
epic (`mb-ww58`). The three stated priorities are `P1`-and-below features.

Either the load-time epic outranks all three — in which case none of this starts soon
and the order is academic — or its `P0` label no longer reflects intent.
Both are defensible; what is not defensible is leaving two contradictory priority
signals in the tracker.

**Fix:** decide which stream is actually next and re-label the other, so `tbd ready`
tells whoever picks up work the same thing this review does.

### R7 — Low: two beads share the Phase 1B label

`mb-h51g` (*Phase 1B: hardened generic Git acquisition*) and `mb-ew38` (*Phase 1B:
generic URL open and offline reuse*) carry the same phase name.
Only `mb-ew38` holds the trust and status dependencies.
Anyone scheduling “Phase 1B” has to read both to learn which one is gated.

**Fix:** rename to distinguish acquisition from serving, or merge them and let the
single bead carry both dependencies.

## Design assessment

**No materially better architecture was found for this order, and the alternatives are
worth recording as considered rather than passed over.**

*Should priority 2 skip the cache and stream from the GitHub API?* No.
The measured argument stands: a blobless clone plus background backfill puts real bytes
in a directory that grep, an editor, and an agent can all read, and history, blame, and
diff then work through the shipped Git pipeline with no provider code.
An API-backed viewer would re-implement all of it and still not survive going offline.

*Should the GitHub model wait until a PR view needs it, instead of Phase 4 up front?*
The design review already argued this and its reasoning holds — letting one API response
shape become the model is a worse failure than modeling early.
The coverage-oracle requirement added during that review is what keeps the model
falsifiable in the meantime.

*Should status and cache share more?* They already share the one thing that matters, the
clean predicate. Sharing more would couple a feature about local working state to a
feature about remote acquisition, which is the coupling the plans deliberately avoid.

The one structural thing this order exposes is that **the repository-library plan is
carrying two products**: a generic Git cache (priority 2) and a GitHub provider
(priority 3). They have different dependencies, different risk profiles, and now
different priorities.
`mb-90va` already tracks splitting Phases 4–8 into their own plan once Phase 2 lands;
the stated priorities are an argument for doing it sooner, because priority 3 is about
to be scheduled independently of priority 2.

## Suggested order

Taking the findings together, the order that the dependencies actually permit:

| # | Work | Gated by |
| --- | --- | --- |
| 1 | Git-status measurement gate (R5) | nothing |
| 2 | Git-status Phase 1 backend (`mb-u4mf`) | the measurement above |
| 3 | Git-status Phase 2 panel (`mb-vibn`) | Phase 1 |
| 4 | HTML trust `mb-cun0`, then `mb-vib1` (R1) | nothing — can run in parallel with 1–3 |
| 5 | Repository-library Phase 0 and 1A (R4) | nothing — can run in parallel with 1–3 |
| 6 | Phase 1B acquisition and URL open, with web-URL normalization (R2) | 2, 4, 5 |
| 7 | Phase 2 primitives, scoped by R3 | 6 |
| 8 | Phase 4 GitHub model, then 5, 6, 7 | 7 |

Rows 4 and 5 are the useful observation: neither depends on Git status, so the trust
workstream and the format foundation can proceed alongside priority 1 rather than after
it. That is what keeps R1 from simply adding its cost to the end of the schedule.

## References

- [Git status and working-tree diffs](../specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md)
- [Repository library and open from a Git URL](../specs/active/plan-2026-08-11-open-repo-from-git-url.md)
- [HTML rendering and an explicit content-trust model](../specs/active/plan-2026-08-06-html-rendering-and-trust-model.md)
- [Git and comparison sources](../architecture/arch-git-and-comparison-sources.md)
- [Repository-library phasing and GitHub content model](review-2026-08-26-repository-library-and-github-model.md)

## Status Addendum — 2026-08-27, after independent review

An [independent review](review-2026-08-27-independent-design-review.md) of the same
material corrected two things here.
Findings are not rewritten; this records what changed.

**R1 was over-severed.** It was filed as a Blocker.
The dependency is real and the sequencing consequence stands, but nothing in this plan
is *incorrect* because of it — the plans already stated that serving is gated, and the
failure mode is a wrong estimate rather than a wrong design.
High is the accurate severity, and the review’s own severity table says Blocker is for a
correctness, security, or soundness failure.

**R1’s Fix option 2 restated the existing posture.** It proposed a narrower deliverable
that ships acquisition and inspection while serving stays gated — which is what the plan
already said at `3d04a78` ("Cache storage and clone components may land before that
gate; serving fetched content may not"). Offering it as a choice implied a change that
was not one. The genuine choice is option 1: schedule the trust chain deliberately, in
parallel, because it depends on nothing here.

**R2’s framing understated the problem it named.** Calling web-URL reduction “pure
string work on a decade-stable shape” was true of the host and path-prefix parsing and
false of the ref/path split, which is genuinely ambiguous and needs the cloned ref list
to resolve.
The revision in `f46bc26` solved it correctly regardless, and the independent
review credits that; the understatement is recorded because a reader taking the original
framing at face value would have scoped the work too small.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
