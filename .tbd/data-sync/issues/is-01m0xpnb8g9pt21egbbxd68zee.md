---
type: is
id: is-01m0xpnb8g9pt21egbbxd68zee
title: Make catalog predicate semantics runtime-independent and exact
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
refs:
  - kind: pr
    url: https://github.com/jlevy/fdu/pull/47
    at: 2026-08-26T00:14:07.222Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/74
    at: 2026-08-26T00:14:07.224Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/commit/3183888808b366b5ba1c381dec1cbb18b49d969e
    at: 2026-08-26T00:33:50.032Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/32915125191
    at: 2026-08-26T00:33:50.034Z
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0tytbmjsb46bnmh5134r5tg
created_at: 2026-08-26T00:14:01.987Z
updated_at: 2026-08-26T00:33:50.299Z
closed_at: 2026-08-26T00:33:50.298Z
close_reason: MetaBrowser now defines catalog suffix semantics explicitly instead of inheriting Python-version-specific pathlib behavior, validates exact predicate shape, and proves provider behavior in the conformance suite. Commit 3183888 passed clean make format, make verify, protected pre-push verification, and exact-head CI on Python 3.12, 3.13, and 3.14.
resolution: null
duplicate_of: null
---
Exact-head alignment finding from FDU PR #47 at 0558c7eff1b91a1dca052d4259dbe3751f6ffcd0. The new spec declares the ..foo suffix finding false after checking CPython 3.11-3.13, but MetaBrowser supports 3.12-3.14 and currently delegates catalog matching to PurePosixPath.suffix. Verified with uv: PurePosixPath("..foo").suffix is ".foo" on 3.12/3.13 and "" on 3.14; "foo." likewise changes from "" to ".". The same MetaBrowser provider therefore answers the same CatalogQuery differently by supported runtime, and FDU's explicit terminal_suffix matches only the pre-3.14 behavior. Define catalog terminal suffix semantics directly in the MetaBrowser contract, independent of pathlib, and use them in PythonInventoryHandle. Recommended rule already implemented by FDU: the last dot begins a suffix when it is neither the first nor final character, so ".gitignore" and "foo." have none while "..foo" has ".foo". Also reject ancestor_names "." and ".." in MetaBrowser so both engines refuse path components that canonical relative paths can never expose. Update architecture prose, contract/provider/conformance tests, and FDU agreement fixtures; no runtime-version branching or adapter-side filtering.
