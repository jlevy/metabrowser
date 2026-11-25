- **A pinned Markdown file’s front matter is the file’s own.** On a served mirror, a
  GitHub address, or a checkout opened with `--ref`, the Document view of a Markdown
  file whose YAML front matter is valid no longer says its frontmatter could not be
  read: the server parses front matter from the file’s own bytes, as it does in a served
  folder, whatever text the page sends to render in the file’s place, and the wiki
  preprocessing copies front matter as written instead of reading its last key as a
  heading.

- **A front matter error is shown once.** When a file’s front matter does not parse, the
  document shows one Frontmatter error notice, and the Diagnostics disclosure no longer
  lists the same error as a raw entry.
  Under the untrusted profile the page draws the notice, where before only its words ran
  into the top of the document.
  `/api/kpress/render` keeps the error in `diagnostics` and the reason in
  `frontmatter_error_detail`; its inert `html` no longer holds KPress’s notice.
