---
type: is
id: is-01m1dt40nmqvb9k1dpewnyk06m
title: "Residual: inventory walk still 28% slower than main after the perf fixes"
kind: bug
status: open
priority: 1
version: 10
labels: []
dependencies:
  - type: blocks
    target: is-01m2fafd1v8d5pakt6r7zxw5n8
child_order_hints:
  - is-01m2gwtgp8rs2e4x0e77f64y8f
created_at: 2026-09-01T06:22:19.315Z
updated_at: 2026-09-20T15:42:04.605Z
---
After the two fixes in mb-0y68, the 60,000-file A/B still shows a gap:

  main    2,071 ms median
  stack   2,652 ms median   (+581 ms, +28%)

cProfile of the walk to settled on that corpus, top frames by tottime:

  0.283  0.534    64,420  dataclasses.py:1781 _replace
  0.260  0.260 1,953,529  dict.get
  0.254  0.254   125,525  <string>:2 __init__      (generated dataclass __init__)
  0.208  0.208    60,000  posix.DirEntry.stat
  0.146  0.237   248,826  contract.py require_canonical_inventory_path
  0.111  0.111 1,282,847  builtins.getattr

The shape of the residual is the double representation. Each entry is built as a
contract InventoryEntry (validated), converted to the provider's retained FsEntry
via _internal_entry, mutated one to three times with dataclasses.replace in the
walker path (python_inventory.py:3129, 3312, 3395), and converted back to
InventoryEntry on read. dataclasses.replace is generically slow: a getattr per
field plus a full __init__, which is where the 1.28M getattr and 125k generated
__init__ calls come from.

This is the same duplication the design review names as F1/mb-gwlw, showing up as
a measurable cost rather than an argument. Options, cheapest first: avoid replace
in the walker where only aggregate fields change and the path fields are already
validated; or let the provider retain one representation instead of two.

Do not attempt this without re-running the A/B: the measurement harness is
/tmp/ab.py style timing of 'metab CORPUS --api /api/index/meta' over
bench_serving's 60k synthetic corpus, three runs, median.

Related: the release revalidation in mb-afdb measures walk completion with a browser attached on a quiet machine and should settle whether this residual still holds on the final release commit.

## Notes

STATUS AFTER exp-035 (2026-09-15): still open, and no longer a v0.10.0 release blocker.

exp-035 accepted v0.10.0 without this being fixed, by scoping the first-row gate to the
corpus class it was calibrated from. The release gate's value did not move: the
quiet-machine recalibration it asked for lands on the same 350 ms. What changed is that
the flat 300k corpus is now measured against performance-budgets-flat-stress.toml, which
ratchets it at current behavior instead of judging it by a number derived from
repository-shaped fan-out.

So this bead's residual is now CARRIED DEBT rather than a blocker, and it is stated as
that in the load-time plan's "Debt Carried into v0.10.0" section and in CHANGELOG.md's
known-limitations entry for 0.10.0.

The residual was decomposed into three tracked beads during this round:
  mb-qvw4  walk under an attached browser, 1.62-1.78x on the flat shape
  mb-qtgj  /api/catalog at 300k rows, 663 ms -> 2,575 ms
  mb-zc3p  Long Tasks appearing where v0.9.1 had none

Root cause is unchanged and is this bead's subject: a browser attached during a walk
pays for an entry query, a contract entry, a projection, a decoration and a wire record
per discovered entry, about 14 us per entry on the delivery path. Paying it down means
not building a per-entry contract object for entries the store already admitted, which
is structural work, not constant tuning. exp-035 measured the constants and they are
worth about 4% between them.

When this is fixed, lower the flat-stress ratchet to the new behavior.

2026-09-20: status returned to open (was in_progress). Nobody is actively working this; as
the notes above state, the residual is carried debt for v0.10.0 and the live work sits in
the successor beads mb-qvw4, mb-qtgj and mb-zc3p. in_progress overstated it.
