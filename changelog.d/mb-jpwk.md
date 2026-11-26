- **A guided review’s file cards are built from the bar Changes draws.** In a pull
  request’s or a stack’s Guided Review, each file’s card now takes its bar and chevron
  from the one builder a file in Changes uses, so the two look and act alike: the bar
  shows the pointer a file’s bar does, and a card’s one-line notice keeps its inset when
  the card is open ([Diff File Bar](docs/design-system.md#diff-file-bar)).

- **Plugin authors:** the diff plugin’s `guidePatchDrawer().disclose(section, folded)`
  makes the bar and chevron that fold a file’s card in Changes and returns them, for a
  page that draws its own card; it no longer takes a bar and a trigger the page built
  ([Declared Dependencies](docs/plugins.md#declared-dependencies)).
