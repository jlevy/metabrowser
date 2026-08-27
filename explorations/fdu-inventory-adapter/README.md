# Exact-Wheel fdu Inventory Adapter Spike

This experiment measures the cost and semantic fit of fdu’s opened-root API against
MetaBrowser’s unchanged inventory-provider contract.
It is not the production adapter.
The experiment installs an exact fdu wheel, injects a backend directly into the existing
coordinator, and leaves the shipping provider factory and default Python provider alone.

## Reproduce the Experiment

The measured revisions are:

- MetaBrowser contract revision: `3183888808b366b5ba1c381dec1cbb18b49d969e`
- fdu opened-root revision: `0583a1a`
- wheel SHA-256: `80a077ba17f979a40f30a8dcfe59b2ceeba39285cf556543d78066b9dc5279c0`

From the MetaBrowser checkout, run:

```bash
# First build from an fdu checkout detached at revision 0583a1a:
cd <fdu-checkout>/crates/fdu-py
uv run --frozen --only-group dev maturin build --locked --release --out <artifact-dir>

# Then return to this MetaBrowser checkout:
wheel=../fdu-artifacts/0583a1a/fdu-0.1.0-cp312-abi3-macosx_11_0_arm64.whl
PYTHONPATH=src:tests:explorations/fdu-inventory-adapter \
  uv --config-file uv.toml run --frozen --with "$wheel" \
  python explorations/fdu-inventory-adapter/run.py \
  --wheel "$wheel" \
  --corpus .

# Strictly type-check the spike against that same installed wheel:
uv --config-file uv.toml run --frozen --with "$wheel" bash -c \
  'basedpyright --project explorations/fdu-inventory-adapter/pyrightconfig.json \
  --pythonpath "$(command -v python)"'
```

The runner verifies the wheel digest and fails if Python imports fdu from the sibling
source checkout. It writes `evidence.json`, normalizing machine paths and generated
session identifiers during serialization, then applies MetaBrowser’s pinned formatter.

## What the Disposable Adapter Does

fdu owns the filesystem walk, retained index, progressive commits, journal, observation,
refresh, versions, and shutdown.
The adapter owns only asynchronous scheduling and contract translation, with one
deliberate exception for measurement: each query-bearing read materializes the complete
native flat projection and invokes MetaBrowser’s current Python projection oracle over
that temporary image.

This exception makes otherwise hidden duplication visible.
The probe records native calls and pages, materialized rows and path bytes, child-bucket
sorts, full-result sorts, aggregate passes, returned rows, CPU time, and wall time.
The temporary image is rebuilt for every read and is never retained between requests.

The adapter does not:

- register `fdu` in the shipping provider factory
- change `METABROWSER_INVENTORY_PROVIDER`
- walk the filesystem in Python
- add MetaBrowser vocabulary, an executor, or an event loop to fdu
- shell out to the standalone fdu command
- hide a missing semantic with a fabricated value

## Results

The installed-wheel application lifecycle passes end to end:

- cold open and a useful progressive read
- transition to the settled watching phase
- native live mutation and host change delivery
- coherent reread of the changed file
- explicit refresh with complete path accounting
- root replacement with a new provider session
- iterator-only cancellation followed by a successful read
- concurrent idempotent close with no surviving poll worker

Iterator cancellation joined in about 239 ms in the recorded run, within the adapter’s
250 ms native poll interval.
The live mutation was delivered and the changed file was coherent on reread.
The recorded run produced a reset; an earlier run at the same revisions produced an
ordinary invalidation naming the root and changed file.
That timing-dependent difference is valid under the current native journal contract and
is why the durable golden session must use a scripted observation source.

Nine of the twelve registered provider-conformance cases pass unchanged.
A tenth, the complete semantic digest, matches every filesystem fact, order, aggregate,
filter, and catalog record; its assertion fails only because diagnostics correctly
identify the provider as `fdu-spike` instead of `python`.

The other two failures identify contract decisions:

- **Resource refusal:** MetaBrowser waits only for `ready`, `watching`, or `failed`, and
  expects a file-budget refusal to remain `watching`. fdu enters the terminal `stopped`
  phase because a resource-stopped root must not start observation or admit expanding
  refreshes.
- **Journal capacity:** with a capacity of one, one refresh can create several native
  commits, including state transitions.
  fdu therefore returns an honest reset where the unchanged test expects one replayable
  application-level batch.
  The revised contract must define capacity and replay in provider-batch terms and allow
  one active iterator.

Eleven of thirteen selected route and SSE tests pass through the injected fdu backend.
The failures are:

- A test that pauses the private Python walker and requires the public status to remain
  `scanning`. That seam cannot pause native discovery and should become a provider-owned
  scripted discovery barrier.
- Recursive directory deletion produces two visible invalidation envelopes instead of
  the one coalesced envelope asserted by the current SSE test.
  Provider verification and host publication need one explicit coalescing boundary.

## Measured Client-Side Duplication

On the fully provisioned MetaBrowser checkout, one bundled eight-query read materialized
8,830 entries and 412,836 bytes of relative paths, rebuilt 470 child buckets, performed
four full-result sorts and four aggregate passes, and returned 9,071 rows.
It took about 852 ms wall time in the recorded run and reached about 13 MB of traced
Python allocation. The count includes ignored dependency trees because the unchanged
MetaBrowser contract retains ignored entries and exposes them to queries; a source-only
checkout measured 791 materialized entries and about 98 ms before dependencies were
installed.

These measurements support four native additions, each tied to observed work:

1. Opaque path-ordered continuations remove complete flat materialization and exact
   suffix counting.
2. Maintained registry and navigation dimensions remove the navigation-wide pass.
3. Maintained time and catalog orderings remove repeated full-result sorts.
4. Native filtered-tree and rollup projections remove the temporary Python entry graph
   and aggregate passes.

The measurement does not justify a generic native “query engine” or MetaBrowser-specific
query enum. Each maintained structure should have a named bounded projection and a
measured item above that it eliminates.

## Golden Session Direction

The durable integration test should record a small deterministic session, not preserve
this performance runner as a golden.
One scripted observation source should drive the real verification and commit path,
while a normalizer removes only generated session IDs, timestamps, durations, OS
metadata, and platform path encodings.

The session should retain full stable payloads for:

- open configuration and derived scope and semantic identities
- every committed version, state transition, issue, impact domain, and dirty path
- complete bounded read requests, projections, continuations, and work counters
- refresh requests and receipts
- iterator cancellation, root replacement, and close
- normalized CLI and Python answers for the same one-shot fixture
- MetaBrowser route responses and SSE envelopes derived from those commits

Critical invariants remain ordinary assertions: versions never move inside a read,
continuations conserve rows, a reset replaces detailed invalidations, resource refusal
never expands, iterator cancellation preserves the handle, close leaves no worker, and
CLI/Python normalized answers agree.
This combination gives broad transparent-box coverage without hundreds of hand-written
integration tests or a snapshot that can be updated without understanding its diff.

## Disposition

Keep `probe.py`, `run.py`, this document, and the normalized evidence artifact as the
reproducible Phase 3A record.
Delete `adapter.py` before closing the spike bead.
Phase 3B should first revise the shared contract and Python oracle; Phase 3C should then
implement only the native projections justified by these measurements and replace the
temporary materializing adapter with a thin production handle.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
