- **A native stack has a page of its own.** `/stack/<n>` shows GitHub stack `<n>` as one
  comparison, from its bottom pull request’s merge base to its top one’s head, holding
  only the files some pull request in the stack changes, so a change the base branch
  merged in is left out.
  Its header lists the stack’s pull requests from top to base, and its **Files**,
  **Docs**, and **Changes** tabs draw that comparison as a pull request’s do, each file
  naming the layers that change it by their place, such as “2/4”, a chip that opens the
  file in that layer. A pull request the top does not contain is named instead, and adds
  no file. The page follows the stack as a pull request’s page follows its head, and
  offers a new comparison rather than swapping it in while you read.
  Each stack menu opens it from a first row, **Whole stack**
  ([The Stack Page](docs/project/architecture/arch-github-pull-requests.md#the-stack-page)).

- **Plugin routes:** `GET /api/plugin/github/stack` answers a stack’s members, the
  members its top lacks, its comparison’s address, and each file’s layers, and
  `GET /api/plugin/github/stack-comparison` that comparison as a diff document.
  `pull-rendered-diff` and `pull-image` take `stack=<n>` in place of `number` and admit
  the stack’s current pair alone.
  The diff view’s `render` and `summary` take a `fileMarks` hook that puts a host’s
  links on each file’s row and bar.
