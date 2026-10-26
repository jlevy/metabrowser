---
type: is
id: is-01m5wd8cpaee3kbv2yth4am7ef
title: "Dependency refresh after 0.12.0: serving stack, TypeScript 7, vendored highlight.js, biome"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-26T15:28:54.985Z
updated_at: 2026-10-26T15:28:54.985Z
---
Deliberately deferred out of the 0.12.0 release on 2026-10-26 so the release carries the security fix and nothing else. Nothing here is security-driven: `uv audit --frozen` reports no known vulnerabilities in all 66 Python packages, and `npm audit` is clean once tryscript is 0.3.1.

Reason for deferring: the 0.12.0 acceptance bar is that nothing destabilizes existing behavior. A 25-package runtime upgrade taken in the same change would invalidate every differential and leave no way to attribute a regression. Sequence them: tag 0.12.0 on the dependency set the evidence was taken against, then do this pass with its own `make verify` and its own differential.

What is waiting, from `uv lock --upgrade --dry-run` and `npm outdated` on 2026-10-26:

- Serving stack, the risky group: starlette 1.3.1 to 1.7.0 and uvicorn 0.49.0 to 0.54.0. These are the ASGI server; route behavior, header handling, lifespan and event-stream behavior all sit on them, and the page-connection work makes the event-stream path load-bearing.
- pydantic 2.13.4 to 2.14.1 with pydantic-core 2.46.4 to 2.50.1, typer 0.26.8 to 0.27.3, ruff 0.15.20 to 0.17.0, nh3 0.3.6 to 0.3.7 (the sanitizer, used on pull-request text), plus about twenty smaller ones.
- TypeScript 6.0.3 to 7.0.2, a MAJOR. Expect new diagnostics against the fully strict tsconfig.json gate.
- @highlightjs/cdn-assets 11.9.0 to 11.12.0. This is a VENDORED SHIPPED asset: it changes rendered highlighting output, so it invalidates browser-differential screenshots and must be taken with fresh evidence, not alongside other work.
- @biomejs/biome 2.5.2 to 2.5.15, and lefthook 2.1.9 to 2.2.2. The biome bump was ATTEMPTED on 2026-10-26 and reverted: it needs `biome migrate` because biome.json pins the 2.5.2 schema, and it raises the new `noDescendingSpecificity` rule against existing CSS, which `--error-on-warnings` turns into a lint-check failure. First flagged file: src/metabrowser/builtin_plugins/folder/file_type_summary.css:105 against :101. It also rewraps a selector in builtin_plugins/diff/styles.css, cosmetic and semantically identical.

Keep the 14-day cool-off: uv.toml's exclude-newer and .npmrc's min-release-age=14 enforce it. First-party jlevy packages are exempt by the owner's standing decision.
