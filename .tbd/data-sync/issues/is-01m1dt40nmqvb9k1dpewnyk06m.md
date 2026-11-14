---
type: is
id: is-01m1dt40nmqvb9k1dpewnyk06m
title: "Residual: inventory walk still 28% slower than main after the perf fixes"
kind: bug
status: open
priority: 1
version: 13
spec_path: docs/project/specs/active/plan-2026-09-15-flat-tree-delivery-cost.md
labels: []
dependencies: []
parent_id: is-01m2hs64m7nfagfxyf7b0hxrhr
child_order_hints:
  - is-01m2gwtgp8rs2e4x0e77f64y8f
created_at: 2026-09-01T06:22:19.315Z
updated_at: 2026-11-14T18:48:38.695Z
---
After mb-0y68's fixes, the 60,000-file A/B on 2026-09-01 still showed the walk 28% slower than main before the provider refactor (2,652 ms against 2,071 ms median). The profile pointed at the double representation: each entry is built as a validated contract InventoryEntry, converted to the provider's retained FsEntry (_internal_entry, python_inventory.py:515), adjusted with dataclasses.replace on several walker and aggregate paths, and converted back on read. That is still the shape on main.

Since v0.10.0 this is carried debt, not a release blocker (exp-035; CHANGELOG.md 0.10.0 Known limitations). It is the structural fix the flat-tree epic mb-odrb names: stop building a per-entry contract object for entries the store already admitted. Its measured symptoms are mb-qvw4, mb-qtgj and mb-zc3p; the load-time plan's H72 row names this bead.

Measure before and after with interleaved build comparisons (devtools/compare_builds.py) on the 300k flat corpus, and lower the performance-budgets-flat-stress.toml ratchet when it lands.

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
