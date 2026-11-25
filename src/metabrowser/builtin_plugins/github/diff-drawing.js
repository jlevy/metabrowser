// How a pull request's page and a stack's draw their diffs: Docs' documents and Changes'
// files, which a guided step's whole documents share. One module, so a stack's Docs opens
// as a pull request's does (docs/project/specs/active/plan-2026-11-24-stack-review.md).

/** The File type group the Docs tab shows, in the diff's `group=` vocabulary. */
export const DOCS_GROUP = "type:docs";

/** The preference the Docs tab remembers its Diff | Current choice as, apart from the
 * `diff.show` that Changes, a commit's page and a patch share, so a choice on one tab does
 * not move the other. */
export const DOCS_SHOW_PREFERENCE = "github.docs.show";

/**
 * How Docs draws a document, which a Markdown file a guided step cites whole shares
 * (`loadDrawDocument`), so it opens as the Docs tab opens it: every fold open, Unified with
 * no layout choice, since a rendered document has no layout and its Source reads as its
 * Rendered does in one column, and on the new version (Current), remembered apart from
 * Changes' `diff.show`. An option Docs gives its documents belongs here, so both take it.
 */
export const DOCS_DRAWING = Object.freeze({
  unfold: true,
  layout: /** @type {const} */ ("unified"),
  show: /** @type {const} */ ("current"),
  showPreference: DOCS_SHOW_PREFERENCE,
});

/**
 * How Changes draws a file, which a YAML or JSON file a guided step cites whole shares
 * (`loadDrawDocument`): the diff view's own defaults, so it opens as Changes opens it, on
 * Diff as `diff.show` remembers it, its long runs folded, in the reader's layout. Docs lists
 * neither format: they are the `data` File type, and Docs the `docs` one
 * (`recommended-file-types.toml`). An option Changes gives its files belongs here, so both
 * take it.
 */
export const CHANGES_DRAWING = Object.freeze({});
