- **A link’s own title moves into its link card.** A link in a Markdown file or a
  folder’s README that carries a title its author wrote, as
  `[setup](setup.md "How to set it up")` does, now shows that title in its link card, in
  quotation marks as the author’s, rather than as the browser’s own tooltip beside the
  card, so the reader sees one tooltip; so does a link to another site.
  An image’s title inside such a link moves into the card the same way, and an image the
  page does not load, inside it, has its address in the card in place of a tooltip of
  its own. The tooltip a link to the branch being browsed was given, “Open the
  corresponding path in the currently served working tree”, which never showed in
  rendered text, is gone: the link’s card says it opens in the served working tree.

- **Plugin SDK:** the runtime `metabrowser.loadRepositoryLinks()` answers registers each
  link its `enhance` reads through the page SDK it is given, whose `previewLink` and
  `forgetPreview` give the link its link card and take it away, with the element it was
  given as the link’s root, for a target the resolver opens here, a rendered diff’s link
  to a file of its head (`view-head`), or a page on another site (`{kind: "external",
  url}`); its unreleased `WORKING_TREE_TITLE` is gone
  ([Data and Navigation](docs/plugins.md#data-and-navigation)). The runtime has not been
  released, so `PLUGIN_SDK_VERSION` is unchanged.
