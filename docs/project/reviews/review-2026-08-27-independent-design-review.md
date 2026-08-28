# Review: Independent Design Review of the Status, Cache, and Provider Plans

**Date:** 2026-08-27

**Author:** Independent reviewer (LLM-assisted)

**Status:** Complete.
Findings are open; no plan has been revised in response yet.

**Scope:** The architecture and planned design at `f46bc26` on
`design/git-status-and-cache-phasing`, reviewed against the same stated delivery order
as the
[prior delivery review](review-2026-08-27-delivery-order-for-status-cache-and-providers.md):

1. Git status working cleanly in the Git tab;
2. pointing Metabrowser at any GitHub repository URL and having it check out the right
   repository from the local cache **and open the file or directory the URL named**; and
3. cached GitHub data and pull-request browsing.

Read: the
[Git-status plan](../specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md),
the
[repository-library plan](../specs/active/plan-2026-08-11-open-repo-from-git-url.md),
the
[GitHub provider plan](../specs/active/plan-2026-08-27-github-provider-and-pull-requests.md),
the
[HTML trust plan](../specs/active/plan-2026-08-06-html-rendering-and-trust-model.md),
[Git and comparison sources](../architecture/arch-git-and-comparison-sources.md), the
bead graph, the `f46bc26` diff, the pre-revision plan at `3d04a78`, and the shipped code
in `src/metabrowser/git/`, `src/metabrowser/diff/`, and `src/metabrowser/static/`.
Porcelain-v2 record shapes, the intent-to-add null-OID encoding, the full proposed
status argument vector, and the index-rewrite behavior of plain `git status` were
reproduced against git 2.50.1 rather than taken from the plans.

This review deliberately does not re-derive the prior review’s findings.
It reports what that review missed, and it challenges that review and the `f46bc26`
revision where the evidence disagrees.

## Verdict

**The layering is right, the modeling discipline is unusually good, and the plans are
still not ready to size priority 2.** Two design-level contradictions survived both the
prior review and the revision: the revised URL-opening promise names a rendering surface
that neither ships nor is scheduled (D1), and the blobless acquisition strategy
contradicts the plan’s own offline and no-network guarantees in a way its own research
already observed (D2). Both decide what priority 2 costs, and both belong in
repository-library Phase 0 as recorded decisions, not discoveries.

The `f46bc26` revision is a real improvement — the trust chain is now a named scheduling
fact, the plan split is the right structure, and the Phase 0 gates are the right
instinct — but its execution left dangling cross-references and stale phase numbers in
load-bearing places (D6), put one item on the wrong deferral list (D7), and gave the
Git-status measurement gate deliverables that only the unwritten implementation can
produce (D8). The prior review was substantively correct on every finding this review
checked, but R1 was over-severed and partly restated the plan’s existing posture as a
new fix (D12), and R2’s “pure string work” framing understated the problem the revision
then had to solve properly.

Everything else found is repairable in place and none of it changes the delivery order
itself: status first remains correct, and the prior review’s observation that the trust
chain and format foundation can run in parallel with it stands.

## Findings

### D1 — High: opening a URL’s file at `<ref>` has no rendering surface when `<ref>` is not the pinned revision

**New finding.** The revised variants table promises “root at `<ref>`” and “file
`<path>` at `<ref>`” ([plan](../specs/active/plan-2026-08-11-open-repo-from-git-url.md)
lines 564–575), and the acceptance criteria promise “a `/blob/<ref>/<path>` URL opens
that file” (line 1042). But the cache entry is an ordinary checkout **pinned to
`active_revision`** — the clone’s default `HEAD` — and Metabrowser’s browser grammar has
exactly two content address spaces: `/view/<path>` over the working tree and
`/commit/<rev>[/<inner>]` over one commit’s *change set* (`docs/architecture.md` lines
333–335). There is no route that serves file content or a tree listing at an arbitrary
revision (`src/metabrowser/git/routes.py` lines 268–274), and `/commit/<rev>/<file>`
shows the file’s diff within that commit, not the file at that revision.

So the design resolves the ref/path split correctly and then has nowhere to open the
result unless the resolved ref happens to be the pinned revision.
The common case — `/blob/main/...` on a fresh clone — works through `/view/`. Every
other case fails the promise: a tag, a feature branch, a `/blob/<sha>/...` permalink,
and even `main` itself on a cache hit after upstream moved (cache hits perform no fetch,
so the pinned tree is main-as-of-clone).
The plan’s fallback covers “no prefix resolves” but never says what happens when the ref
resolves and is not the pinned revision.
Opening the working-tree version silently would be exactly the “landed on the wrong
thing” failure this revision was written to eliminate.

The same section commits to line and column anchors “becom[ing] a selection within the
file”. `navigation.js` fragments are document locations (heading anchors); no line-range
selection primitive is in evidence in the shipped text view, so this is a second
unpriced browser surface, smaller but real.

**Fix:** add a mapping column to the variants table — each selection to the browser
route that renders it — and scope Phase 1B honestly.
The defensible near scope: the ref disambiguates the path split; the path opens in the
pinned working tree when it exists there; a resolved ref that differs from the pinned
revision is reported with the revision that is actually being shown; `/commit/<oid>`
URLs go to the existing commit view.
Then either schedule a revision-content view or a checkout-at-requested-ref acquisition
policy as the named follow-on that completes the promise, and price the line-anchor
selection or defer it explicitly.
The acceptance criteria must match whichever scope is chosen.

### D2 — High: blobless acquisition contradicts the offline and no-network guarantees, and the plan never reconciles them

**New finding.** The plan guarantees “a cache hit an offline operation.
Network work begins only for a missing entry or an explicit refresh” (line 79) and the
acceptance criteria repeat it.
The leading acquisition strategy is blobless clone with background backfill, serving
immediately (lines 671–698). A blobless checkout lazily fetches missing blobs from the
promisor remote the moment a Git command touches them — and the shipped read paths do:
the project’s own research measured commit detail at ~0.5 s cold because
`--numstat -M -C` needs file content, and observed blame failing outright with
`could not fetch … from promisor remote` when the network was cut, concluding “a
blobless clone is not self-sufficient until backfill completes”
([research](../../research/research-2026-08-11-repo-cache-and-git-url-open.md) lines
259–283).

The plan absorbed that observation only as “run backfill promptly” and “honest partial
states”. It never states the consequences:

- until backfill completes, ordinary reads on a served entry make **network requests
  from server request paths**, bounded only by the subprocess timeout — against the
  repository’s own rule about bounding synchronous work on request paths;
- offline, those same reads fail as a generic `GitCommandError` → 500, not as a typed
  “content not local” state, even though File Diff Format already has the honest
  vocabulary (`deferred`, `unavailable`); and
- the offline-reuse acceptance test as worded ("a cache hit needs no network") passes on
  the open and is false one click later.

**Fix:** decide the lazy-fetch policy in Phase 0 and record it beside the version-gate
table. The clean options: serve reads with lazy fetch disabled (the `--no-lazy-fetch`
global option / `GIT_NO_LAZY_FETCH`; recent Git, so it needs its own floor row — verify
the exact version in Phase 0) and map missing-object failures to
`deferred`/`unavailable`, letting backfill completion flip them to `ready`; or gate
blobless acquisition on that floor and fall back to full clone below it; or accept lazy
fetch explicitly, bound it, and rewrite the offline guarantee to say what is actually
true ("history and tree structure offline; file content per `object_state`"). Add “read
of a not-yet-backfilled blob, online and offline” to the Phase 1B acceptance list beside
interrupted clone — it is currently the one adverse path there with no stated outcome.

### D3 — Medium: the bead graph lets Phase 1B-a start without the Phase 1A foundation it writes records with

**New finding.** `mb-h51g` (*Phase 1B-a: hardened generic Git acquisition*) is blocked
only by `mb-ire2` (Phase 0). Its own specification publishes `repository.yml` and
`state.yml` — “immutable repository identity plus atomic state, no-replace publication”
— which are Phase 1A contracts, atomic-YAML primitives, and locks (`mb-4gnu`). The
plan’s dependency map says “1B … depends on 1A” (line 929), but after the a/b split only
`mb-ew38` (1B-b) carries the `mb-4gnu` edge.
Once `mb-ire2` closes, `tbd ready` will offer acquisition work whose storage layer does
not exist — precisely the drift the plan warns about when it says a constraint that
lives only in prose is one nobody is reminded of.

**Fix:** add the `mb-4gnu` → `mb-h51g` dependency.

### D4 — Medium: the status generation includes index identity, so unrelated terminal Git commands churn it

**New finding.** The list generation hashes “resolved per-worktree index identity”
alongside `HEAD`, the normalized sorted records, and the policies
([status plan](../specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md)
lines 511–520). Reproduced against git 2.50.1: a plain `git status` in a terminal
rewrites `.git/index` (refreshed stat cache) without changing any status fact.
Every such touch therefore changes Metabrowser’s generation: the `ETag` misses, the
route’s 304 path never fires, and a selected one-file diff — whose request carries the
generation — takes the 409 `stale_status` path and re-materializes an identical
document. The plan itself warns that stat-dirty re-hashing is the non-amortizing cost of
`GIT_OPTIONAL_LOCKS=0`; this design multiplies that cost on exactly the workflows (a
terminal beside the browser) the coordinator’s debounce is being measured for.

The normalized records already capture everything user-visible — object IDs, stages,
`XY` pairs — so two acquisitions with identical records are the same snapshot for every
purpose the generation serves.
Index identity is the right input for the *adapter’s* before/after race sampling, where
the plan already uses it.

**Fix:** derive the generation from `HEAD` state, the normalized sorted records, and the
acquisition policies only; keep index identity in the materialization-window sampling.
If there is a reason the extra sensitivity is wanted, the plan should record it, because
as written it reads as an accident with a measurable cost.

### D5 — Medium: the scroll-origin constraint argues from a premise the codebase has since falsified

**New finding.** The status plan’s “Changes above a virtualized History” section (lines
253–307) states that `git-panel.js` “passes the scroller’s raw `scrollTop`” (line 262),
that the defect “is tracked as `mb-180g`” (line 279), and that whatever fix `mb-180g`
takes “must land before Changes is built on top of it” (line 285). `mb-180g` is closed:
`0715a66` landed the caller-owned conversion — `historyOrigin()` in `git-panel.js`
(lines 916–944, applied at 1090–1096), cached, invalidated on height change, and written
to count *any* sibling above the list — and `git-history-window.js` now documents the
coordinate contract in its header (lines 9–16). The plan predates the fix (`65af050`,
the reconcile commit, came before it) and was not updated by `f46bc26`, which touched
only its phase list.

This matters beyond staleness, because the section’s prohibition — “What is **not**
acceptable is one scroller with an offset correction applied at the call site” (line
300\) — now describes the shipped mechanism.
Two of its three supporting arguments no longer hold: re-derivation cost is answered by
the cached, invalidated origin, and the segment-rebase budget is unaffected by a bounded
origin offset once the conversion is applied consistently.
The argument that survives is real but different in kind: a user-toggled,
variable-height Changes block collapsing mid-scroll produces a visible viewport jump,
which is a UX reason to prefer separate scrollers, not a correctness reason.

**Fix:** update the section to the landed state — the fix chose conversion at the
boundary, cite `0715a66` — and re-derive the structural requirement from what is now
true. Either the prohibition stands on the jump argument alone (say so), or the
conversion is acceptable for Changes too and the baseline changes.
Keep the Phase 2 deep-scroll test with Changes expanded and collapsed either way; it is
the check that outlives the prose.

### D6 — Medium: the plan split is incomplete — dangling anchors, stale phase numbers, and stranded provider requirements

**Challenges `f46bc26`.** The split itself is right; its execution left both documents
pointing at each other’s missing pieces:

- The repository-library plan’s “Decisions Deferred to Their Evidence Phase” still says
  “Phase 4 selects the physical snapshot sharding” and “Phase 5 selects REST, GraphQL,
  or a hybrid” (lines 1021–1029) — its Phase 4 is now large-repository support, Phase 5
  does not exist, and the in-document anchor
  `#transport-is-already-partly-decided-and-the-model-should-say-so` points at a heading
  that moved to the provider plan.
- The provider plan says “the discovery lands in Phase 5” and “What remains open for
  Phase 5” (lines 88, 90, 109, 120) — its acquisition phase is Phase 2 — and its line
  119 links to `#decisions-deferred-to-their-evidence-phase`, a section that stayed in
  the donor document.
- Provider security requirements are stranded in the donor: the repository-library
  plan’s Security and Trust section still owns “Provider records are validated before
  publication and bounded by file, field, and collection limits… Markdown and HTML from
  issues, pull requests, and comments use the existing untrusted rendering policy”
  (lines 797–801). The provider plan — the document a provider implementer will read —
  has no security section and never mentions the untrusted rendering path.
  The three provider testing bullets are duplicated verbatim in both plans, so they now
  have two authorities.

**Fix:** move the transport-decision text and the provider-record security requirements
into the provider plan, leave one-line cross-references behind, renumber the stale phase
mentions, and deduplicate the testing bullets.
`make verify` passed with these dangling anchors in place; see the non-blocking
suggestion about an anchor check.

### D7 — Medium: compiled-schema drift checking is on the wrong deferral list

**Challenges the prior review (R4’s fix) and `f46bc26`.** Phase 1A’s deferrable list
(lines 832–838) — adopted from the prior review’s trim candidates — includes
“compiled-schema drift checking” under the rationale that each deferrable item “only
pays off once a *second* reader exists.”
That rationale is true for the migration harness and the format history.
It is false for drift checking: a committed compiled schema can go stale against its
model within a **single** release — one model edit without regeneration — and the same
plan states that an enforced contract requires both layers because “model-only
validation is insufficient: an enforced boundary without a compiled schema can silently
accept undeclared fields” (lines 368–375). Deferring the drift check while still
packaging compiled schemas makes `status: enforced` quietly weaker than the plan’s own
artifact-profile section requires; it is the exact failure mode R8 of the
[2026-08-26 review](review-2026-08-26-repository-library-and-github-model.md) closed.

**Fix:** move drift checking to the non-negotiable list — it is one `--check` invocation
in CI beside the compile step — or, if Phase 1A ships without compiled schemas at all,
record explicitly that enforced records are model-only until they land.
What is not coherent is packaging compiled schemas whose agreement with the models
nothing checks.

### D8 — Medium: the Git-status Phase 0 gate promises measurements only the unwritten implementation can produce

**Challenges the prior review (R5’s fix) as executed in `f46bc26`.** The new Phase 0
“produces no code” and must “record status and one-file-diff latency, bytes, retained
memory, and representative browser row cost” (`mb-r5gn`; plan lines 956–975). Of those,
only the Git-side numbers are measurable before Phase 1 exists: acquisition latency,
output bytes, and record counts on the corpus, and the raw cost of the underlying diff
commands. “Peak Python retained bytes” is a property of the not-yet-written parser and
service; browser time-to-first-row and DOM cost at the row cap (measurement list, lines
661–674) are properties of Phase 2. As written, the gate either blocks Phase 1 on
numbers that require Phase 1, or gets satisfied by proxy numbers presented as the real
thing — which defeats the point of separating it.

**Fix:** split the measurement list by phase.
Phase 0 owns the corpus and the Git-command measurements, which are sufficient to choose
the timeout, debounce, entry/byte budgets, the submodule option, the copy-detection
verdict, and the `--untracked-files=all` go/no-go — every decision the gate exists for.
If a browser row budget is wanted up front, admit the throwaway DOM benchmark as gate
tooling rather than claiming no code.
Phases 1 and 2 keep in-implementation attribution *against* the Phase 0 budgets, which
is what the plan’s rollout section already implies.

### D9 — Medium: the provider snapshot store has no reclamation rule

**New finding.** The repository-library plan states the principle: “retention without a
reclamation rule is how a cache silently becomes the largest directory in a home folder”
— and gives `staging/`, `trash/`, and quarantine their rules at creation time (lines
327–351). The provider store does not apply its own lesson: `objects/` accumulates one
immutable snapshot per observed change of every fetched resource, `manifests/` one file
per refresh, forever
([provider plan](../specs/active/plan-2026-08-27-github-provider-and-pull-requests.md)
lines 266–307), and the only stated removal is entry-level explicit purge (lines
425–428). Old manifests are never superseded-and-swept, and nothing defines which
snapshots are still referenced.
An actively refreshed pull request accretes without bound by design.

**Fix:** state the rule when the directories are created, in provider Phase 2, matching
the pattern the cache plan already set: retain the current manifest plus a small named
number of predecessors; sweep object snapshots referenced by no retained manifest, under
the entry lock; count provider bytes in the generic size accounting.
Or record the deferral explicitly with the disk consequence, so it is a decision rather
than an accumulation.

### D10 — Low: counts in architecture-doc prose contradict the maintained tables beside them

**New finding.**
[Git and comparison sources](../architecture/arch-git-and-comparison-sources.md) says
“Three things in a working repository have **no object id**” above a four-row table
(line 53), and “Four read-only routes, registered as `GIT_ROUTES`” above a five-row
table (line 199). The second is the document’s own cautionary tale in miniature: when
`/api/git/summary` landed, the named check forced the *table* to update and the sentence
kept its stale numeral — exactly why the repository guidance says never to write a count
into prose that nothing maintains.

**Fix:** delete the numerals ("The read-only routes, registered as…"; “Several things in
a working repository have no object id” or restructure the sentence).
The named checks already own the real inventory.

### D11 — Low: ref resolution is unspecified against the namespace a clone actually has

**New finding.** “Try the longest prefix that names a real ref” (repository-library
plan, lines 589–614) is the right algorithm, but in a fresh clone only the default
branch exists under `refs/heads/`; every other branch is `refs/remotes/origin/<name>`. A
resolver that checks “is this a ref” naively fails for every non-default branch — the
main case the feature exists for.
Separately, current GitHub raw URLs also take the form
`raw.githubusercontent.com/<owner>/<repo>/refs/heads/<branch>/<path>` (and
`refs/tags/…`), which the variants table’s `<ref>/<path>` row only handles if the
candidate matcher understands the `refs/heads/` prefix.
The Phase 1B goldens (lines 890–893) cover a slash-containing branch but neither of
these.

**Fix:** specify the resolution order — exact object ID, `refs/tags/<name>`,
`refs/remotes/origin/<name>`, `refs/heads/<name>` — note that Git’s own precedence
prefers refnames over ambiguous short OIDs, strip `refs/heads/`/`refs/tags/` prefixes
for the raw host, and add both cases to the goldens list.

### D12 — Low: the prior review’s R1 was over-severed and partly restated the plan’s existing posture

**Challenges the prior review.** R1 ("Blocker: priority 2’s critical path runs through a
plan that was not prioritized") claimed the trust dependency was “invisible from the
plans that were prioritized.”
At `3d04a78` the plan named the gate in four places — including, verbatim, “Cache
storage and clone components may land before that gate; serving fetched content may not”
(line 129–131) — and the bead graph carried `mb-ew38` ← `mb-vib1` throughout.
R1’s Fix option 2 ("a narrower priority 2 that does not serve fetched content") is that
existing sentence restated as a new alternative.
The genuinely new contribution — surfacing `mb-cun0` at the head of the chain and
stating the estimate consequence — was real and worth making, and `f46bc26`’s “The Gate
That Decides When This Ships” section is the right response.
But under this repository’s own severity vocabulary, a plan that understates a
dependency it names and the tracker enforces is a High documentation-of-cost defect, not
a Blocker correctness failure.
The distinction matters: Blocker inflation in reviews is how real blockers stop
commanding attention.

Related, smaller: R2 called web-URL reduction “pure string work on a shape GitHub has
kept stable for a decade.”
The revision’s own analysis disproved that — the ref/path split is unresolvable by
string work and required the post-acquisition candidate-split design — and R2’s
suggestion that pull-request URLs “fail with a message” was rightly rejected in favor of
opening the repository and naming what cannot yet render.
No action needed; recorded so the next reviewer knows the framing was checked.

## Design assessment

Taking the six designs the scope names in turn, with alternatives.

**Porcelain-v2 parsing model: sound, and its riskiest claims verify.** The record
families, the second NUL-delimited rename path, the intent-to-add `1 .A N…` null-OID
encoding, and the full proposed argument vector were all reproduced exactly against git
2.50.1. The fail-closed rule (no resynchronization after structural corruption) is
correct for a parser whose records drive `git cat-file` arguments.
The rename-only baseline with `C` as parser-level coverage is the right reading of
`status.renames` versus `--find-renames`, and the documented `/commit` versus `/status`
copy asymmetry is an honest trade.
No better alternative found.

**Manufactured-identity and generation model: sound, one over-inclusion.** The
arch-doc’s rule — no object ID means a manufactured identity plus stated validity rules
— is applied consistently across the history cursor (session ID + scope fingerprint),
the status generation, and cache `state.yml`, and the four typed history failures are
the model to copy. The one deviation is D4: the status generation includes an input
(index stat identity) whose changes carry no information the normalized records lack.

**Cache publication state machine: sound; the gap is upstream of it.** Claim → staged
clone → validate → no-replace rename → serve is right, the identity/state file split
answers the 2026-08-26 review’s R2 correctly, the `last_opened_at` write-failure
tolerance is a well-judged detail, and the staging/trash/quarantine reclamation rules
are the kind of thing usually discovered on a full disk instead of designed.
The unresolved piece is not the state machine but what “published and serving” means for
a blobless entry (D2). The alternative — streaming from the GitHub API instead of
caching — was already correctly rejected in both prior reviews; nothing here reopens it.

**URL reduction and ref/path resolution: right shape, two gaps.** A declarative
host-pattern table upstream of the cache, emitting an ordinary clone URL plus an inert
selection, is the correct way to hold the provider-neutral identity boundary, and
resolving the ambiguous split after acquisition against the real ref list is strictly
better than any parse-time guess — the revision’s best design decision.
The gaps are what happens after resolution (D1) and which ref namespace resolution
consults (D11). One alternative worth recording: now that a per-host table exists,
terminal-`.git` equivalence for exactly the recognized hosts could live in that table,
so `https://github.com/o/r` and `https://github.com/o/r.git` stop producing two full
clones of one repository.
That revisits a recorded decision (R10 of the 2026-08-26 review) deliberately: the
conservative rule was adopted when no provider knowledge existed anywhere, and the
reduction table changed that premise for the hosts it names.
Generic hosts stay conservative either way.

**SoftSchema contract policy: sound and appropriately stricter than upstream.** Host
registry binding over document-declared schemas, both validation layers for enforced
records, the new-contract-version rule for any structural accept-set change, and the
honest first-party cool-off analysis all hold up; the coverage-oracle addition in the
provider plan closes the real blind spot of a hand-authored corpus (a model that cannot
be falsified until adapter work) without letting one API response become the model.
The one incoherence is the drift-check deferral (D7).

**Provider snapshot/manifest model: the consistency model is right; the retention model
is missing.** Immutable content-addressed snapshots, completed sync manifests, and
atomic current pointers correctly prevent the mixed-state reads that per-file atomic
writes cannot (R6 of the 2026-08-26 review), and keeping retrieval metadata out of
snapshot identity is what lets conditional responses reuse unchanged objects.
The gap is D9. The GraphQL-presumption honesty ("Transport is already partly decided")
is a model of recording a constraint instead of hiding it — it just lives at a stale
phase number in the wrong document’s anchor (D6).

**On the delivery order itself:** status-first stands, for the `is_clean` reason the
prior review established.
The prior review’s parallelism observation (trust chain and format foundation alongside
priority 1) also stands and remains the most schedule-relevant fact.
What this review adds: priority 2 grew in `f46bc26` — web-URL reduction, candidate-split
resolution, selection opening — and D1 and D2 are both Phase 0-shaped decisions that
change its scope, so no estimate for priority 2 made before they are resolved will
survive contact. The R6 priority contradiction (eight open `P0` load-time items versus
`P1` feature priorities) was verified as still present in `tbd ready` and still
undecided; it is tracked in the review-parent bead and needs no new finding, only the
decision.

## Non-blocking suggestions

- **Add a Markdown anchor/link check to the docs gates.** `make verify` passed with two
  dangling in-document anchors introduced by the plan split (D6). This repository
  prefers a check to a sentence, and cross-document anchors are exactly the drift class
  its named-table checks already catch elsewhere.
- **State the Phase 1 semantics of `If-None-Match`.** The status plan binds 304 to the
  coordinator’s knowledge, but the coordinator is Phase 2; in Phase 1 a conditional
  request can only reacquire-and-compare, saving serialization and transfer, not
  acquisition. One sentence prevents an implementer from inventing a TTL.
- **Specify the entry-ID digest framing.** The ID hashes scope and two raw paths; since
  POSIX paths exclude NUL, NUL-delimited field framing makes the digest unambiguous, and
  the parser tests should pin it.
- **Record the conflict-comparison base choice.** Left = stage 1 (base) versus the
  worktree result is defensible, but stage 2 (ours) answers “what does this merge change
  on my branch” and is what some users will expect; one sentence naming the choice and
  the deferred three-way view prevents relitigating it in Phase 2 review.

## Checked and dismissed as benign

Recorded so the next reviewer does not repeat the work:

- **Porcelain claims against real Git.** The full proposed status argument vector runs
  clean on git 2.50.1; intent-to-add emits `1 .A N…` with `000000` modes and all-zero
  OIDs exactly as the plan’s validator rule assumes; rename records carry the original
  path as a second NUL-delimited token; `git status` accepts `--find-renames` and has no
  `--find-copies`. The plan’s Git floors and option semantics are accurately researched.
- **Arch doc versus code.** `GIT_COMMON_ARGS`, the nine scrubbed repository-pinning
  variables, the typed error taxonomy, `run_git`/`spawn_git_process`/
  `terminate_git_process`, and bytes-out all match `src/metabrowser/git/process.py`; the
  `DiffSource` port is the four methods the doc shows (`diff/adapters/base.py`); the
  immutable adapter really runs `-M50 -C` (`diff/adapters/git.py`), so the documented
  `/commit`-versus-`/status` rename asymmetry is real; `GIT_ROUTES` matches the arch
  table and `tests/test_git_arch_doc.py` exists to keep it so.
- **CLI boundary claim.** `root: Path | None` at `src/metabrowser/cli/main.py:228`, as
  the plan states; the `str | None` change is genuinely required.
- **Trust-chain claims.** `mb-ew38` ← `mb-vib1` ← `mb-cun0` and `mb-ew38` ← `mb-u4mf`
  verified in the tracker; the `f46bc26` “Gate That Decides When This Ships” section
  matches the graph.
- **Strict unknown-record failure.** Failing the whole acquisition on an unknown
  porcelain record family is correct, not brittle: new families appear only with
  requested options, and resynchronizing after corruption risks attaching metadata to
  the wrong path.
- **Longest-prefix ref matching.** Matches GitHub’s observable resolution for
  slash-containing branches; the open issue is namespace, not order (D11).
- **Single status process per root, join-or-supersede coalescing, and the
  summary-deferral ordering** are all consistent with the shipped panel’s loading
  discipline and need no change.
- **`no-store` plus `ETag`.** Coherent here: the application holds the validator in
  memory and revalidates explicitly; nothing needs the HTTP cache to store the body.
- **Provider plan’s independence claim.** “Gated on the cache existing and on nothing
  else” is accurate transitively — the trust chain gates the cache’s serving path, so it
  is upstream of, not parallel to, this plan.

## References

- [Git status and working-tree diffs](../specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md)
- [Repository library and open from a Git URL](../specs/active/plan-2026-08-11-open-repo-from-git-url.md)
- [GitHub provider — content model, acquisition, and pull requests](../specs/active/plan-2026-08-27-github-provider-and-pull-requests.md)
- [HTML rendering and an explicit content-trust model](../specs/active/plan-2026-08-06-html-rendering-and-trust-model.md)
- [Git and comparison sources](../architecture/arch-git-and-comparison-sources.md)
- [Delivery order for Git status, the repository cache, and providers](review-2026-08-27-delivery-order-for-status-cache-and-providers.md)
- [Repository-library phasing and GitHub content model](review-2026-08-26-repository-library-and-github-model.md)
- [Repository-cache research](../../research/research-2026-08-11-repo-cache-and-git-url-open.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
