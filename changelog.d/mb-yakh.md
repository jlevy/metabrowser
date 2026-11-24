- Guided Review is a new tab, shown first, on a pull request whose description carries a
  `guided-review` block: the description as its overview, then the author’s ordered
  review steps, each showing the diff it cites as Changes draws it: a line range as one
  hunk, or a whole file with its long runs folded behind bars you expand.
  A list of the steps leads the guide, with the description as step 0, and arrows page
  through them; every part names a step the same way, “Step 3: title”.
  A pull request with a guide opens on it at `/pull/<n>`, Conversation moves to
  `/pull/<n>/conversation`, and there the block is a card that opens the guide.
  An out-of-date guide still shows its steps, under a notice that names the revision it
  was written for, the commits since, and the steps that cite changed files.
  The block is the first use of the new external format
  `metabrowser.collection:Collection/v1`, a general ordered list of annotated items not
  tied to pull requests, versioned by its contract ID, and a guide goes out of date when
  the pull request’s head or merge base changes
  ([Guided Review](docs/reviewing-pull-requests.md#guided-review)). First contributed in
  #599.
- **App contract:** `metab --plugins --json` lists `diff` among the github plugin’s
  `requires`, since Guided Review draws its excerpts with the diff plugin’s renderer.
  The macOS app reads the list as it is and needs no change.
