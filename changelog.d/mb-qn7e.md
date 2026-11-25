- **A changed Markdown file chooses Full, Concise, or Source.** On a pull request’s
  Changes and Docs, the file’s chooser offers **Full**, every block, and **Concise**,
  each change with a few unchanged blocks beside it and the runs between folded, in
  place of Rendered. Changes opens on Concise, and Docs on Full, or on Concise for a long
  document. Where a file can only show Source, both rendered views stay in place,
  unavailable, and say why.
  YAML and JSON keep **Rendered** | **Source**
  ([Rendered Markdown in Changes](docs/reviewing-pull-requests.md#rendered-markdown-in-changes)).

- **A Markdown fold is the diff’s fold bar.** A run of unchanged blocks folds behind the
  same blue bar a code file’s long run of changed lines does, and opens and closes as it
  does ([Fold Expanders](docs/design-system.md#fold-expanders)). A long fold’s blocks
  are fetched when it opens, or when a link goes to a heading inside it, so a long
  document with a few edits loads in the size of its edits.

- **Docs and Changes open without drawing hidden Source.** A changed file with a
  rendered view draws its Source lines only when Source shows and you reach it, so a
  long document behind its rendered view no longer slows the page as it opens.

- **A very long Markdown diff draws as you scroll.** A rendered Markdown file longer
  than Docs opens in Full draws its blocks a part at a time near the viewport, keeping
  its place in the scroll bar; a link into a part not drawn yet draws it first, and
  printing draws all of it.
  In such a file, find in page and Select All reach only the parts drawn.
  Reaching a 3,408-block book, its worst main-thread task fell from 351 ms to 64 ms.

- **Route:** `github/pull-rendered-diff` takes `view=full`, `view=concise`, or
  `view=prefer-full`, and `blocks=I-J` for a range of a Markdown projection’s blocks.
  Its Markdown answer says its `view` and lists its `folds`, each fold’s `at`, `count`,
  and source `lines`, and a withheld fold’s `withheld` and the `ids` of the headings it
  holds; an invalid parameter is answered `400` with the code `invalid_rendered_diff`.
