- In a repository folder, a branch or tag chosen in the Files chooser now follows it:
  when you commit on the branch shown, or your own `git fetch` moves `origin/main`, the
  page goes to the new commit by itself within a few seconds, on the same file or folder
  when the new commit has it, or at the root.
  Metabrowser reads the checkout’s refs to see the move, fetches nothing into your
  checkout, and writes nothing in it; where it keeps a store of the origin, such a page
  also keeps that store fetched, quietly, about once a freshness window.
  A branch you delete while it is shown keeps its last commit on the page, and the row
  at the foot of the navigation pane says the branch no longer exists.
  A commit opened by its ID stays that commit, even while it is the tip of the branch
  you came from, and **Working tree** is always the files on disk
  ([browsing history](docs/browsing-history.md#branches-and-tags-of-a-local-checkout)).
  `GET /api/source/status` reports such a revision with `follows` true, `latest`, and
  `probe_every_s`, and `POST /api/source/refresh` with `{"for": "page"}` answers
  `probed` on a folder that shows one, where a folder with no store of its origin
  answered `409`.
