---
type: is
id: is-01m87dze3k6ya58f9qa31pmazh
title: "softschema: refusing a mapping's undeclared keys costs time quadratic in their number (one error record per key, each canonicalizing the whole mapping)"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-24T18:44:32.497Z
updated_at: 2026-11-24T18:44:32.497Z
---
Upstream fix for softschema (first-party, jlevy/softschema), found by D1 of security review D on #677. Metabrowser does not patch it; it works around it.

In softschema 0.8.1, `validate_structural` (validate.py:224) keeps every jsonschema error, and `_structural_error_properties` (validate.py:297-310) yields one record per undeclared key of an `additionalProperties: false` object. Each record runs `_canonical` over the whole offending mapping twice: once in `structural_error_record` (errors.py:220-221) and once in `render_structural_message` (errors.py:167). A mapping with K undeclared keys therefore costs O(K^2).

Measured through metabrowser's `parse_guide` (guided_review.py) before the workaround, on a 10-core Mac at a load average of 81 to 168 (2026-11-24): 4,000 undeclared keys took 9.6 s on the collection and 11.3 s on an item; about 13,000 keys at the 64 KiB description bound took 135.8 s and 104.6 s. Review D's cProfile of the 2,000-key case put 14.7 of 15.6 s in `structural_error_record` (8.0 million `_canonical` calls).

Fix upstream:
- canonicalize an error's instance once per jsonschema error, not once per offending property, and render the per-property message without re-canonicalizing the instance;
- cap the records `validate_structural` keeps (or let a caller cap them), so a document cannot make validation write an unbounded error list.

Metabrowser's workaround: `_outside_shape` in `src/metabrowser/builtin_plugins/github/guided_review.py` refuses undeclared keys and lists past MAX_ITEMS / MAX_REFERENCES before `validate_artifact` runs. Once softschema is fixed and the pin raised, re-measure; the walk can stay (it is cheap), but its docstring's cost claim should be updated.
