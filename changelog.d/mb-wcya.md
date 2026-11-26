- **The link card.** A link in rendered text that opens a page in Metabrowser has one
  tooltip, the link card: what kind of object it opens and which, “Pull request #12 ·
  Changes · src/app.py”, its title where the app knows it, and that it opens here, or in
  the served working tree for a link to a branch.
  It appears when the pointer rests on the link and never on focus or a touch, and a
  rest also starts loading what the link opens.
  A card never repeats the link’s own words, and shows a pull request’s state only where
  its data says it. Tooltips on links follow one rule everywhere
  ([Tooltips on Links](docs/design-system.md#tooltips-on-links)).
