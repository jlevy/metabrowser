- Guided PR is a new tab, shown first, on a pull request whose description carries a
  `guided-pr` block: the description as its introduction, then the author’s ordered
  review steps with excerpts from the pull request’s exact diff.
  A list of the steps leads the guide, with the description as step 0, and arrows page
  through them. A pull request with a guide opens on it at `/pull/<n>`, Conversation
  moves to `/pull/<n>/conversation`, and there the block is a card that opens the guide.
  An out-of-date guide still shows its steps, under a notice that names the revision it
  was written for, the commits since, and the steps that cite changed files.
  The block is the first use of the new external format
  `metabrowser.collection:Collection/v1`, an ordered list of annotated items, versioned
  by its contract ID, and a guide goes out of date when the pull request’s head or merge
  base changes ([Guided PR](docs/reviewing-pull-requests.md#guided-pr)). First
  contributed in #599.
