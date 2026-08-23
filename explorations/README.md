# Explorations

Measured-improvement loops.
Each subdirectory is one campaign against one subject: a registry of falsifiable
hypotheses, rounds measured against a control, verdicts under a pre-declared accept
rule, and a ledger generated from the record.

| Loop | Subject |
| --- | --- |
| [performance-loop](performance-loop/README.md) | How fast Metabrowser becomes usable — loading, responsiveness, visual stability, assets, the scan, and the server underneath, using the reusable [Web Performance Framework](../docs/web-performance-framework.md) |

Nothing here runs in CI. An exploration answers a question once; a benchmark defends an
answer forever, and only the second earns a place in the release gate — which is what
[`devtools/bench_serving.py`](../devtools/bench_serving.py) is for.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
