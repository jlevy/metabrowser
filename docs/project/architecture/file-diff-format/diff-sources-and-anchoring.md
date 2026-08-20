# Diff Sources, Context, and Anchoring

**Status:** Partially implemented; each path below states its own status.

[File Diff Format v1](file-diff-format.md) defines *what* a comparison document is.
This document is the first-principles map of *where documents come from*, what a
repository context adds to one, and how that context is validated.
It exists so the design survives the plan spec that produced it: the spec describes a
project, this describes the system.

## Separability

From first principles, viewing a diff is three separable stages:

1. **Acquisition** — obtain the raw material: a `.patch` file on disk, a pair of git
   revisions, a GitHub pull request, an archive of edits.
2. **Modeling** — convert it to a `ChangeSetDocument` and validate it.
3. **Rendering** — project the document.
   The renderer never learns which source produced it.

The stages compose because everything converges on the format, and because unified patch
text is itself a convergence point: GitHub serves any pull request as a unified diff,
git emits one for any pair of trees, and both parse through the same
`parse_unified_patch`. The two routes to the same pull request — GitHub’s `.diff`
download and a local three-dot `git diff` over the same endpoints — produce the same
document, which is the practical test of the separability claim.

## The paths

| # | Path | Pipeline | Status |
| --- | --- | --- | --- |
| 1 | Patch file, standalone | `.patch`/`.diff` → patch source → render | Implemented: browser view and `metab --diff FILE` |
| 2 | Git revisions, local repository | rev pair → git source → render | Implemented: the CLI (`--diff A..B`, single revision, `--diff-check`) and the Git history view, which renders a selected commit’s first-parent comparison through the diff view |
| 3 | GitHub PR as a patch | `gh pr diff N` or the PR’s `.diff` URL → path 1 | Implemented (it is path 1) |
| 4 | GitHub PR over git transport | fetch `refs/pull/N/head` → merge-base → path 2 | Planned: acquisition and composition |
| 5 | Uncommitted states | worktree/index vs `HEAD` → git source | Modeled (snapshot kinds, `generation` tokens); source support planned |
| 6 | Patch anchored to a repository | path 1 + a claimed base revision → validate → enrich | Planned; the oracle it needs is implemented |
| 7 | Hosted metadata (PR conversation) | provider API → plugin | Planned, plugin territory |
| 8 | Document edit history | editor sessions → future source | Format is ready; no source exists |

Statuses are maintained with the code they describe; the roadmap and its issue tracking
live in the
[general diff rendering plan](../../specs/active/plan-2026-08-17-general-diff-rendering.md).

## Context: anchored and unanchored comparisons

A bare patch is self-contained but context-blind.
It asserts “at this line, this text becomes that” and carries only hunk-neighborhood
context, paths, and sometimes abbreviated blob oids.
The format records this honestly: the patch source emits `kind: patch` snapshots and
`empty` content refs — an **unanchored** comparison that never pretends to more identity
than it has.

An **anchored** comparison names real trees: commit oids on the snapshots, `git_object`
content refs on every side.
The git source emits anchored documents.

Context — a repository whose trees the document claims to describe — buys five concrete
things:

1. **Validation.** Does this patch actually describe these trees?
2. **Whole files.** Before/After views need content beyond the hunk window; anchored
   sides resolve through their content refs.
3. **Context expansion.** “Show more lines” reads the base file.
4. **Richer semantics.** A patch file shows a type change as delete-plus-add because
   that is what patch text contains; the git source folds the pair into one
   `type_changed` entry.
   Exact totals for binaries and quality rename scores need the trees too.
5. **A computed base.** A pull request is meaningful against the merge base; context
   lets us compute and verify it instead of trusting the patch.

## Validating context

The validator already exists: **the apply oracle is the definition of “this document
matches these trees.”** `metabrowser.diff.apply` replays a hydrated document against a
base tree and either reproduces the target tree byte-for-byte or refuses with the first
mismatch. `metab --diff A..B --diff-check` is its CLI face; equal tree hashes are the
proof.

Two validation levels, by cost:

- **Oid precheck.** When the document carries content refs or the patch carries index
  lines, compare claimed oids against the repository before touching content.
  Cheap, catches wrong-base immediately, cannot prove hunk fidelity.
- **Full replay.** The oracle.
  Byte-exact, including modes, entry types, and missing final newlines.

Anchoring a foreign patch (path 6) is the marrying surface between these: resolve each
`old` side by path at the claimed revision, run the oracle, and annotate each file clean
or conflicted — `git apply --check` semantics, expressed through the model, with the
successful result upgraded to an anchored document.

## Acquisition and materialization

Sources that must fetch or unpack before they can model — a pull request’s refs, a patch
hydrating against a base, an archive — share one materialization concern: bounded,
transient cache directories that the normal serving path routes into.
This is deliberately one mechanism, not one per source; the
[nav container design](../arch-nav-containers.md) describes the shared routing and the
plan spec describes the git-specific acquisition workflow.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
