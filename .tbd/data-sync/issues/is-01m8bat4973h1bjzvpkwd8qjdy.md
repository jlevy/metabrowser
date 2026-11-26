---
type: is
id: is-01m8bat4973h1bjzvpkwd8qjdy
title: "Spec: In-app link resolution for every rendered text"
kind: epic
status: closed
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/874
    at: 2026-11-26T07:52:54.494Z
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
child_order_hints:
  - is-01m8batevm97ram0xe6qr81j30
  - is-01m8batfbvgswamcwp6dnnpqh3
  - is-01m8batfxy4fy1yjw8saszwj9z
  - is-01m8batgfdp0vjve5p9bpyy35n
  - is-01m8bath1w87tng37agprs65de
  - is-01m8bathnhy6pkgn4hmjd87hb1
  - is-01m8bp7ce37pgee1zpr3wrq5q6
  - is-01m8bkxf108ayt40j2hhjkrxm5
created_at: 2026-11-26T07:06:10.598Z
updated_at: 2026-11-26T10:46:34.703Z
closed_at: 2026-11-26T10:46:34.703Z
close_reason: "Merged Metabrowser PR #874 at 24d368b05dd3be0024305f126f96a4a207f74436 after passing CI and independent follow-up reviews."
resolution: null
duplicate_of: null
---
One pure resolver decides what a link in rendered text opens: relative links open the file at the text's revision, github.com links into the served repository open the matching in-app page (file, folder, root, pull request and tabs, commit, pulls), and everything else stays external. Surfaces: Markdown files and READMEs, pull request texts, Guided Review notes, commit bodies, rendered diffs. Owner request 2026-11-26.
