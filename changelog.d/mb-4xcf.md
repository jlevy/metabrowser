- **A link’s own title moves into its link card.** A link in a Markdown file or a
  folder’s README that carries a title its author wrote, as
  `[setup](setup.md "How to set it up")` does, now shows that title in its link card, in
  quotation marks as the author’s, rather than as the browser’s own tooltip beside the
  card, so the reader sees one tooltip; so does a link to another site.
  The tooltip a link to the branch being browsed was given, “Open the corresponding path
  in the currently served working tree”, which never showed in rendered text, is gone:
  the link’s card says it opens in the served working tree.

- **Plugin SDK:** the runtime `metabrowser.loadRepositoryLinks()` answers gives each
  link its link card through `previewLink(root, anchor, target, mb, options)`,
  `forgetPreview(anchor)`, and `disposePreviews(root)`, for a target the resolver opens
  here, a rendered diff’s link to a file of its head (`view-head`), or a page on another
  site (`{kind: "external", url}`), and its `enhance` registers each link it reads with
  the element it was given; its unreleased `WORKING_TREE_TITLE` is gone
  ([Data and Navigation](docs/plugins.md#data-and-navigation)). The runtime has not been
  released, so `PLUGIN_SDK_VERSION` is unchanged.
