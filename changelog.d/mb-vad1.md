- **A native stack has a page of its own.** `/stack/<n>` shows GitHub stack `<n>` as one
  comparison, from its bottom pull request’s merge base to its top one’s head, holding
  only the files some pull request in the stack changes, so a change the base branch
  merged in is left out.
  Its header lists the stack’s pull requests from top to base, and its **Docs** and
  **Changes** tabs draw that comparison as a pull request’s do.
  A pull request the top does not contain is named instead, and adds no file.
  The page follows the stack as a pull request’s page follows its head, and offers a new
  comparison rather than swapping it in while you read; the one you are reading stays
  while a pull request is fetched, and keeps loading after the stack moves.
  A pull request it could not fetch is named, with a **Retry**; Retry and **Show the new
  comparison** take number keys, as a pull request’s status line’s controls do.
  Each stack menu opens it from a first row, **Whole stack**
  ([The Stack Page](docs/project/architecture/arch-github-pull-requests.md#the-stack-page)).

- **Plugin routes:** `GET /api/plugin/github/stack` answers a stack’s members, each with
  its `author` and `avatar`, the members its top lacks, its top member’s head branch
  (`head_ref`), its comparison’s address, and each file’s layers, and
  `GET /api/plugin/github/stack-comparison` that comparison as a diff document.
  `pull-rendered-diff` and `pull-image` take `stack=<n>` in place of `number` and admit
  the stack’s current pair and its last earlier pairs, which are kept in
  `sources/<slug>/pulls/stack-<n>.snapshots.json`. Each pending member of the `stack`
  answer says whether its fetch was running before its record was read (`fetching`).
  `GET /api/plugin/github/stacks` names a member the repository’s cached list lacks,
  such as a merged one, by its cached record, so its `titles`, `authors`, and `avatars`
  name it as the stack’s page does.
