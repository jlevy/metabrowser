type MetabrowserRenderContext = {
  kind?: string;
  path?: string;
  /** A Git revision, when a surface asks a view for a comparison rather than a file. */
  revision?: string;
  /** Two endpoints, when a surface asks the diff view for a comparison between them. */
  comparison?: {
    left: string;
    right: string;
    base_policy: "direct" | "merge_base";
    route?: string;
    /** The route that serves an image of the head a rendered Markdown file shows, which a
     *  page completes with a path. */
    image_route?: string;
    /** The route that renders one changed Markdown, YAML or JSON file, which a page completes
     *  with its ID. */
    rendered_route?: string;
    /** A pull request's Changes file controls. The head ref opens by branch, a
     *  null ref opens by commit, and a null branch omits the controls. */
    branch?: { ref: string | null } | null;
  };
  /** The owner of a selected comparison read, while its view is mounting. */
  comparisonSignal?: AbortSignal;
  /** One changed file of the comparison, by its path: the diff view draws the comparison
   *  route's one-file answer, as the diff plugin's `mountRenderedFile` asks it to. */
  file?: string;
  /** How the host opens one of a comparison's changed files at its own address, as a pull
   *  request's Changes does at `/pull/<n>/files/<path>`; absent where a file has none. */
  openFile?: (path: string) => void;
  /** How long a comparison's first screen of Markdown files waits for Rendered, for a page
   *  that keeps the comparison out of sight until its handle's `firstScreen` settles. */
  markdownHoldMs?: number;
  /** Where a page that keeps a comparison's Diff summary at its own top wants the diff's
   *  summary drawn, as a commit's page does; or false, where the page draws it itself and the
   *  diff draws none, as a pull request's page does (docs/design-system.md, "Diff Summary"). */
  summaryHost?: HTMLElement;
  summary?: false;
  /** The change set's whole totals, where the page knows more than the comparison's list,
   *  as a commit's page does from the commit's own stats: the diff's summary says them, and
   *  how many files are listed, when that list is cut short at its bound. */
  summaryTotals?: {
    files: number;
    additions: number | null;
    deletions: number | null;
    exact: boolean;
  };
  /** Told the validated comparison a view mounts, so a page that draws its Diff summary
   *  itself has the comparison's files however the diff came by them. */
  onDocument?: (document: Record<string, unknown>) => void;
  /** A diff's File type choice the host kept, which mounts first, and how the host is told
   *  each new choice (null for every type); a pull request's page keeps it across tabs. */
  types?: Array<string> | null;
  onTypes?: (types: Array<string> | null) => void;
  /** A diff narrowed to one fixed File type group, `type:<id>`, with no File type chooser;
   *  every fold of a text diff drawn open, and each Markdown file opened in Full where it
   *  is short enough to draw whole and in Concise otherwise (`prefer-full`, *unfold*);
   *  and what it says when the group holds no file (*emptyText*). A pull request's Docs
   *  tab is `type:docs`, with *unfold*. */
  group?: string | null;
  unfold?: boolean;
  emptyText?: string;
  /** Fixes the diff's layout at Unified whatever the reader's stored choice, with no layout
   *  control and no `L`, as a pull request's Docs tab does. */
  layout?: "unified";
  /** What the diff's Diff | Current chooser opens on before the reader chooses on this
   *  surface (Diff unless the host says Current), and the preference that choice is
   *  remembered as (`diff.show` unless the host keeps its own): a pull request's Docs tab
   *  opens on `"current"` and remembers it as `github.docs.show`. */
  show?: "diff" | "current" | "full";
  /** Render a file card inside a block that supplies the comparison controls. */
  embedded?: boolean;
  showPreference?: string;
  /** A pull request's page: its number, the tab its route names, and how it
   *  asks the shell to open a tab, or another pull request's page, in the URL. */
  number?: number;
  tab?: string;
  open?: (route: MetabrowserPullRoute) => unknown;
  /** A pull request's page opened by a reader's selection in the Pulls tab: what the tab read
   *  of its record, and how long the page waits before it fetches one the cache lacks. */
  reader?: MetabrowserPullReader | null;
  /** The Pulls tab's host, when the shell mounts the list in the tab. */
  pullsNav?: MetabrowserPullsNavHost;
  raw?: unknown;
};

type MetabrowserPullReader = {
  fetchAfterMs: number;
  /** The tab's answer, its catalog verdict header, and when it landed by `Date.now()`. */
  initial: { etag: string | null; body: unknown; verified?: string | null; at?: number } | null;
  /** The tab's read still on its way when the page opened, which the page joins. */
  pending?: Promise<{
    etag: string | null;
    body: unknown;
    verified?: string | null;
    at?: number;
  } | null> | null;
  /** End the pending read: the page that joined it went before it answered. */
  abandon?: () => void;
  /** Whether the key that opened the page is still held, so the page waits to ask. */
  walking?: () => boolean;
};

/** *replace* is a key's skim through the Pulls tab: the history entry is replaced, not pushed.
 *  *file* is one changed file, whose address is `/pull/<n>/files/<path>`. */
type MetabrowserPullRoute = {
  number: number;
  tab: string;
  file?: string;
  /** The page of that number shows the file already: only the address moves. */
  jumped?: boolean;
  reader?: unknown;
  replace?: boolean;
  /** The number is a native stack's, and the address its page, `/stack/<n>[/<tab>]`. */
  stack?: boolean;
};

type MetabrowserPullsNavHost = Readonly<{
  filter: string;
  current: number | null;
  /** The changed file the address names, or null. */
  file: string | null;
  shown: boolean;
  refreshAhead: boolean;
  /** A checkout served as a folder: its list is of its `origin`, read only once shown. */
  checkout: boolean;
  /** The tab's toolbar in the navigation's slot, which the list's filters fill; or null. */
  toolbar?: HTMLElement | null;
  /**
   * The band under the toolbar, outside the panel's scroller, which the list's count and
   * connection lines fill; or null.
   */
  metadata?: HTMLElement | null;
  /**
   * The navigation's one Refresh (static/refresh-plan.js), to which the list provides its
   * own refresh and the shown pull request page's; or null on a page with no Refresh.
   */
  refreshParts?: MetabrowserRefreshParts | null;
  scrollRoot: HTMLElement | null;
  open(route: MetabrowserPullRoute): unknown;
  /** A changed file's address, through the route's encoder; null where a path is not one. */
  fileHref(number: number, path: string): string | null;
  /** A native stack's changed file's address, on its page's Changes; null as `fileHref`. */
  stackFileHref(stack: number, path: string): string | null;
  /** The page of that pull request while it holds the pane, else null. */
  pageFor(number: number): unknown;
  onPageChange(listener: () => void): () => void;
  filterChanged(state: string): void;
}>;

/** What the list's view hands the Pulls tab's host. */
type MetabrowserPullsPanelHandle = Readonly<{
  setShown(shown: boolean): void;
  setCurrent(
    number: number | null,
    file?: string | null,
    /**
     * *preserveScroll* keeps the list where the reader left it; *again* shows the pull
     * request again when the address names the one already current, for an open of the
     * pull request shown (docs/design-system.md, "Navigation Reveals the Item"). *stack*,
     * with no pull request, is the native stack whose own page the address names, whose
     * Whole stack row the list marks.
     */
    options?: { preserveScroll?: boolean; again?: boolean; stack?: number | null },
  ): void;
  setFilter(state: string): void;
  move(delta: -1 | 1, how?: { repeat?: boolean }): boolean;
  released(): void;
  activateAnchor(): boolean;
  /** Space on a pull request's row toggles its changed files in place. */
  toggleFiles(number: number): boolean;
  /** Space on a stack's row, while the list is grouped by stack, opens or closes it. */
  toggleStack(number: number): boolean;
  /**
   * Space on a stack's Whole stack row toggles the stack's changed files in place, under
   * it, as `toggleFiles` does a pull request's.
   */
  toggleStackFiles(stack: number): boolean;
  /**
   * Right and Left on a pull request's row, or a stack's Whole stack row: its changed files
   * open, or close, and Left from a closed one goes to the stack's row it is under. On a
   * stack's row: it opens, or Right goes to its first row, Whole stack, and Left closes it.
   */
  expand(): boolean;
  collapse(): boolean;
  /** The keys of a changed file's row. */
  moveFile(delta: -1 | 1, how?: { repeat?: boolean }): boolean;
  fileLeft(): boolean;
  fileRight(): boolean;
  activateFile(): boolean;
  /**
   * Home (static/main-tabs.js, `goHome`): the list as a fresh load of `/view/` draws it,
   * from the rows it holds and with no read. A view without it keeps what it shows.
   */
  home?(): void;
  dispose(): void;
}>;

type MetabrowserViewSpec = {
  render: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  dispose?: (container: HTMLElement) => void;
  /**
   * What `render` would fetch for a comparison, fetched before the view is shown, at the
   * address `render` asks, so the browser's cache answers the render. The diff view has one.
   */
  prefetch?: (
    comparison: {
      left: string;
      right: string;
      base_policy: "direct" | "merge_base";
      route?: string;
    },
    signal?: AbortSignal,
  ) => Promise<unknown>;
  /**
   * A comparison's File type counts (the comparison route's `view=types` answer), at the
   * address `prefetch` asks. The diff view has one.
   */
  typeCounts?: (
    comparison: {
      left: string;
      right: string;
      base_policy: "direct" | "merge_base";
      route?: string;
    },
    signal?: AbortSignal,
  ) => Promise<unknown>;
  /**
   * The first screen's rendered Markdown of a comparison *raw* answers, asked for ahead of
   * the view, apart from `prefetch`, under the asking page's *signal*. The diff view has one;
   * a comparison that names no rendered route asks for nothing.
   */
  prefetchMarkdown?: (
    comparison: {
      left: string;
      right: string;
      base_policy: "direct" | "merge_base";
      route?: string;
      rendered_route?: string;
    },
    raw: unknown,
    signal: AbortSignal,
  ) => Promise<void>;
  /**
   * A comparison's Diff summary on its own, drawn in *slot* from what `prefetch` or `render`
   * read, for a page that keeps it at its top while the view comes and goes, as a pull
   * request's page does. The diff view has one; null for a comparison it cannot read.
   */
  summary?: (
    slot: HTMLElement,
    ctx: { raw: unknown; openFile: (path: string) => void },
  ) => Promise<{ dispose: () => void } | null>;
  /**
   * The rows a comparison's Diff summary lists, from what `prefetch` or `render` read, for a
   * page that draws the comparison's files in a tree of its own, as the Pulls tab draws a
   * stack's under its Whole stack row. The diff view has one; null for a comparison it
   * cannot read.
   */
  summaryRows?: (raw: unknown) => Promise<MetabrowserChangedFileRow[] | null>;
  /**
   * Switch the served pin through the page's one switch, which the diff view's controls
   * share, for a page whose own controls switch it too, as a pull request's Browse code
   * does. The diff view has one; what follows a switch is the caller's.
   */
  switchPin?: (
    selection: { oid: string; under?: string; view?: string },
    wanted?: () => boolean,
  ) => Promise<
    | { kind: "switched"; href: string | null }
    | { kind: "busy" }
    | { kind: "abandoned" }
    | { kind: "refused"; message: string }
  >;
};

type MetabrowserViewDescriptor = {
  id: string;
  label?: string;
  /** The view tab's declared one-letter key, lowercase; absent when none is declared. */
  key?: string;
  default?: boolean;
  container_class?: string;
  printable?: boolean;
  print_profile?: string;
  render_runtime?: string;
};

type MetabrowserPreparedViewComposition = Readonly<{
  initialView: MetabrowserViewDescriptor | null;
  status: "ready" | "cancelled";
  views: ReadonlyArray<
    Readonly<{ renderer: MetabrowserViewSpec | null; view: MetabrowserViewDescriptor }>
  >;
}>;

type MetabrowserViewLifecycleStage = Readonly<{
  disposers: Array<() => void>;
  cancel(): boolean;
  commit(replace: () => void): boolean;
}>;

type MetabrowserViewCompositionRuntime = Readonly<{
  FACE_WAIT_MS: number;
  /** Give every view tab under `root` its click. */
  bindTabs(root: ParentNode): void;
  /** Select one tab of a view tab bar; false when the bar lacks it. */
  selectTab(bar: HTMLElement, tabId: string): boolean;
  /** Say which of a host's views is in front, and its print state. */
  setActiveView(host: HTMLElement, viewId: string | null | undefined): void;
  /** The stage of `path` in the pane, while that file holds its first paint. */
  stagedFile(pane: HTMLElement, path: string | undefined): HTMLElement | null;
  /** Wait, at most FACE_WAIT_MS, for the faces a staged view's text is set in; `null` when they are there. */
  settleFaces(root: Element | null | undefined): Promise<void> | null;
  createLifecycle(options?: { onDisposeError?: (error: unknown) => void }): Readonly<{
    begin(): MetabrowserViewLifecycleStage;
    disposeActive(): void;
  }>;
  mount(
    container: HTMLElement,
    renderer: MetabrowserViewSpec,
    context: MetabrowserRenderContext,
    disposers: Array<() => void>,
    options?: {
      afterMount?: (container: HTMLElement) => void;
      onError?: (error: unknown) => void;
      renderError?: (container: HTMLElement, error: unknown) => void;
    },
  ): Promise<"mounted" | "cancelled" | "error">;
  prepare(options: {
    kind: string;
    views: Array<MetabrowserViewDescriptor>;
    preferredViewId?: string;
    ensureKindAssets(kind: string): Promise<void>;
    getRegisteredView(kind: string, viewId: string): MetabrowserViewSpec | null | undefined;
    isCurrent?: () => boolean;
  }): Promise<MetabrowserPreparedViewComposition>;
}>;

type MetabrowserNavigationOpenOptions = {
  /** Activate this view when the destination declares it; otherwise use its default. */
  viewId?: string;
  /** Replace the current history entry rather than push one. */
  replace?: boolean;
};

type MetabrowserNavigationApi = Readonly<{
  current(): MetabrowserNavigationTarget | null;
  href(target: MetabrowserNavigationTarget): string;
  open(
    target: MetabrowserNavigationTarget,
    options?: MetabrowserNavigationOpenOptions,
  ): Promise<void>;
  /**
   * Open an in-app page other than a file's in place, by the address a link carries: a
   * pull request's page and its tabs and changed files (`/pull/`), a stack's (`/stack/`),
   * the list (`/pulls`), or a commit (`/commit/`); the address shown is opened again
   * where it is, pushing no history entry. Answers whether the shell opened it:
   * false for any other address, one the shell cannot show yet, or before its tabs have
   * loaded, and the caller then lets the browser follow the link. The shell's tab
   * controller opens it (static/main-tabs.js, `openRoute`).
   */
  openRoute(href: string): boolean;
}>;

type MetabrowserNavigationTarget = Readonly<{
  path: string;
  query?: string;
  fragment?: string;
}>;

type MetabrowserDocumentWidthRuntime = Readonly<{
  DEFAULT: number;
  KEY: string;
  MAX: number;
  MIN: number;
  apply(
    value: unknown,
    persist: boolean,
    dependencies: {
      input: { value: string } | null;
      root: { style: { setProperty(name: string, value: string): void } };
      writePreference(key: string, value: string): void;
    },
  ): number;
  normalize(value: unknown): number;
  readStored(readPreference: (key: string) => string | null): number;
}>;

type MetabrowserRemoteImagesRuntime = Readonly<{
  INPUT_ID: string;
  KEY: string;
  choose(
    blocked: boolean,
    applied: boolean,
    dependencies: { writePreference(key: string, value: string): void; reload(): void },
  ): boolean;
  mount(
    doc: Pick<Document, "getElementById">,
    dependencies: {
      applied(): boolean;
      writePreference(key: string, value: string): void;
      reload(): void;
    },
  ): boolean;
}>;

type MetabrowserRefChipOptions = {
  label?: string;
  kind?: string;
  trunk?: boolean;
  head?: boolean;
  menu?: "inline" | "sibling" | false;
  /** The earlier option for an actionable ref. Actionable chips now open a menu. */
  copy?: "inline" | "sibling" | false;
  ref?: string;
  repository?: string | null;
  snapshot?: string;
  /** The Files source chip is current. Its menu omits in-app navigation. */
  current?: boolean;
};

type MetabrowserRepositoryContext = Readonly<{
  branch: string | null;
  /** Whether `origin` has the branch: in the context the server writes, not the SDK's copy. */
  branch_on_origin?: boolean;
  host: "github.com";
  name: string;
  owner: string;
  revision: string;
  served_prefix: string;
}>;

type MetabrowserNavigationApplyContext = Readonly<{
  source: "startup" | "user" | "popstate";
  pathChanged: boolean;
  isCurrent(): boolean;
  viewId?: string;
}>;

type MetabrowserNavigationController = Readonly<{
  canonicalizePath(path: string, isFolder: boolean): void;
  current(): MetabrowserNavigationTarget | null;
  dispose(): void;
  open(
    target: MetabrowserNavigationTarget,
    options?: { replace?: boolean; viewId?: string },
  ): Promise<unknown>;
  restore(): Promise<unknown>;
  start(): Promise<unknown>;
}>;

type MetabrowserFileRevalidationMarker = Readonly<{ id: number }>;

type MetabrowserFileRevalidationTracker = Readonly<{
  add(path: string): void;
  capture(path: string): MetabrowserFileRevalidationMarker | null;
  clear(): void;
  delete(path: string): boolean;
  has(path: string): boolean;
  keys(): MapIterator<string>;
  settle(path: string, marker: MetabrowserFileRevalidationMarker | null): boolean;
  readonly size: number;
}>;

type MetabrowserPreviewSelection = Readonly<{ folder: boolean; path: string; viewId?: string }>;

type MetabrowserPreviewPanePhase =
  | "starting"
  | "idle"
  | "loading"
  | "content"
  | "error"
  | "unreachable"
  | "external";

/** What the preview pane shows while no rendered view owns it. */
type MetabrowserPreviewPlaceholder = Readonly<
  | { paint: "none" }
  | { paint: "loading"; subject: "preview" | "folder" | "file" }
  | { paint: "idle"; message: string }
>;

type MetabrowserPreviewFailure = Readonly<{
  detail: string;
  kind: "error" | "unreachable";
  summary: string;
}>;

type MetabrowserPreviewPaneLifecycle = Readonly<{
  claim(owner: string, selection?: MetabrowserPreviewSelection): number;
  /** Whether the pane shows or is loading this file selection. */
  holds(path: string): boolean;
  isCurrent(claim: number): boolean;
  placeholder(claim: number): MetabrowserPreviewPlaceholder;
  reconnected(): MetabrowserPreviewSelection | null;
  settle(claim: number, outcome: "content" | "error" | "unreachable"): boolean;
  settleUnclaimed(): MetabrowserPreviewPlaceholder;
  snapshot(): Readonly<{
    claim: number;
    owner: string;
    path: string | null;
    phase: MetabrowserPreviewPanePhase;
  }>;
}>;

/** The shell's text helpers the Files totals are written with (app.js). */
type MetabrowserTreeSummaryFormat = {
  /** A count of files as a count summary paints it, "12,797 files" in its parts. */
  formatCountParts(n: number): MetabrowserCountParts;
  formatSize(bytes: number): string;
};

type MetabrowserNavigationRouteRuntime = Readonly<{
  displayPath(path: string, sourceKind?: "filesystem" | "git_revision"): string;
  /** The GitPath wire of a path on a pinned revision; null when it has an empty segment. */
  attachController(controller: MetabrowserNavigationController): () => void;
  commitFreshFileResponse(options: {
    cacheFile(data: Record<string, unknown>): void;
    cacheValidator(etag: string): void;
    data: Record<string, unknown>;
    etag: string | null;
    evictFile(): void;
    evictValidator(): void;
    isCurrent(): boolean;
  }): "cancelled" | "file" | "folder";
  createFileRevalidationTracker(maxEntries: number): MetabrowserFileRevalidationTracker;
  /** Park a page's connections for the back/forward cache and resume them on a restore. */
  createPageConnections(deps: {
    connections: ReadonlyArray<() => (() => void) | null>;
    rebuild(): void;
    teardown(): void;
  }): Readonly<{
    hidden(persisted: boolean): void;
    parked(): number;
    suspended(): boolean;
    defer(resume: () => void): void;
    shown(persisted: boolean): void;
  }>;
  createPreviewPaneLifecycle(): MetabrowserPreviewPaneLifecycle;
  /** One root-summary request at a time, however many callers ask, spaced by its cost. */
  createRootSummaryRefresh(deps: {
    fetchSummary(): Promise<boolean>;
    wanted(): boolean;
    now(): number;
    setTimer(callback: () => void, ms: number): unknown;
    debounceMs: number;
    minIntervalMs: number;
    costFactor: number;
    maxIntervalMs: number;
  }): Readonly<{
    request(): void;
    resume(): void;
    state(): Readonly<{
      stale: boolean;
      inFlight: boolean;
      armed: boolean;
      notBefore: number | null;
      failures: number;
    }>;
  }>;
  /** The Files totals' navigation metadata line, and its two live-patched figures. */
  treeSummaryHtml(
    summary:
      | {
          files?: unknown;
          size: number;
          ignored_files?: number;
          ignored_size?: number;
        }
      | null
      | undefined,
    fallbackFiles: number | null | undefined,
    fallbackSize: number | null | undefined,
    format: MetabrowserTreeSummaryFormat,
    keepIgnoredLine?: boolean,
  ): string;
  /** What the Files totals line is drawn from: the root's totals, and its ignored line. */
  createRootTotals(options: { gitRevision: boolean; shell?: unknown }): Readonly<{
    fromRootEntry(
      entry:
        | {
            total_files?: unknown;
            total_size?: unknown;
            unignored_files?: unknown;
            unignored_size?: unknown;
          }
        | null
        | undefined,
    ): boolean;
    fromSummary(summary: unknown, status: unknown): void;
    totals(): MetabrowserRootTotals | null;
    keepsIgnoredLine(): boolean;
  }>;
  /** The served root's tracked and ignored totals from its own entry, or null. */
  rootTotalsFromEntry(
    entry:
      | {
          total_files?: unknown;
          total_size?: unknown;
          unignored_files?: unknown;
          unignored_size?: unknown;
        }
      | null
      | undefined,
  ): MetabrowserRootTotals | null;
  treeSummaryCountHtml(
    files: number | null | undefined,
    format: Pick<MetabrowserTreeSummaryFormat, "formatCountParts">,
  ): string;
  treeSummarySizeHtml(
    bytes: number | null | undefined,
    format: Pick<MetabrowserTreeSummaryFormat, "formatSize">,
  ): string;
  createController(options: {
    apply(
      target: MetabrowserNavigationTarget | null,
      context: MetabrowserNavigationApplyContext,
    ): unknown;
    eventTarget?: Pick<Window, "addEventListener" | "removeEventListener">;
    history?: Pick<History, "pushState" | "replaceState">;
    location?: Pick<Location, "pathname" | "search" | "hash">;
  }): MetabrowserNavigationController;
  /** `/commit/<rev>[/<file>]` — the comparison address space. */
  commitHref(revision: string, file?: string): string;
  href(target: MetabrowserNavigationTarget): string;
  navigation: MetabrowserNavigationApi;
  normalizeTarget(target: MetabrowserNavigationTarget): MetabrowserNavigationTarget;
  parse(pathname: string, search?: string, hash?: string): MetabrowserNavigationTarget | null;
  parseCommit(pathname: string): Readonly<{ revision: string; file: string }> | null;
  recoverFailedExpandedFolders(options: {
    panel: HTMLElement | null;
    revision: boolean;
    recent: boolean;
    load(path: string, children: HTMLElement): unknown;
  }): void;
  replaceFileSnapshot(
    previous: Map<string, Record<string, unknown>>,
    entries: Array<Record<string, unknown> & { path: string }>,
    callbacks: {
      install(next: Map<string, Record<string, unknown>>): void;
      retire(path: string): void;
      upsert(entry: Record<string, unknown> & { path: string }): void;
    },
  ): Map<string, Record<string, unknown>>;
  /** Describe a Quick File open that threw instead of settling. */
  openFailureOutcome(
    error: unknown,
  ): Readonly<{ message: string; status: "error" | "unreachable" }>;
  /** Mark a rejected fetch as an unreachable server; aborts pass through. */
  requestFailure(error: unknown): unknown;
  /** Mark a rejected body read as an unreachable server; aborts and JSON syntax errors pass through. */
  responseBodyFailure(error: unknown): unknown;
  settleFileSelectionFailure(options: {
    cached: boolean;
    claim: MetabrowserPreviewClaim;
    error: unknown;
    isCurrent(): boolean;
    markForRevalidation(): void;
    pane: MetabrowserPreviewPaneLifecycle;
    path: string;
    showError(failure: MetabrowserPreviewFailure): void;
  }): Readonly<
    { status: "cancelled" } | { message: string; status: "error" | "not-found" | "unreachable" }
  >;
  settleNavigationDependency<T>(
    pending: Promise<T>,
  ): Promise<Readonly<{ status: "ready"; value: T } | { status: "error"; error: unknown }>>;
}>;

type KpressAssetLoading = "classic" | "module" | "resource" | "stylesheet";

type KpressAssetManifestEntry = {
  entry_point: boolean;
  id: string;
  loading: KpressAssetLoading;
  output_path?: string;
  path: string;
  public_url?: string;
};

type KpressAssetManifest = {
  assets: Array<KpressAssetManifestEntry>;
  import_map: Record<string, string>;
  schema_version: "kpress-asset-manifest-v2";
};

type KpressRenderPayload = {
  assets: KpressAssetManifest;
  diagnostics?: Array<unknown>;
  html: string;
  /** The version of each served file the document embeds, by `/raw` identity. */
  raw_versions?: Record<string, string>;
};

type DisposableHandle = {
  dispose?: () => void;
  /** Stop progressive work while retaining inert DOM through a pending handoff. */
  cancelPending?: () => void;
  /** Initial useful content is ready; later progressive work stays outside this boundary. */
  ready?: Promise<void>;
};

type MetabrowserRequestErrorRuntime = Readonly<{
  RequestError: new (
    message: string,
    options?: { cause?: unknown; operation?: string; status?: number },
  ) => Error & { operation: string; status: number };
  classifyRequestError(error: unknown): Readonly<{ message: string; retryable: boolean }>;
  isAbortError(error: unknown): boolean;
}>;

type MetabrowserFormatterRuntime = Readonly<{
  /** Abbreviated age and its freshness class — the one age primitive. Its label is for words;
   *  a drawn age is `ageLabel`'s or `ageLabelHtml`'s. */
  age(epochSeconds: number, options?: MetabrowserAgeOptions): { label: string; className: string };
  /** An age as every surface draws one: a span of its label in its freshness class, after
   *  the call site's own class; empty where the time is not known. */
  ageLabel(
    doc: Document,
    epochSeconds: number | null | undefined,
    options?: MetabrowserAgeLabelOptions,
  ): HTMLSpanElement;
  /** `ageLabel` as escaped markup, or "" where the time is not known. */
  ageLabelHtml(
    epochSeconds: number | null | undefined,
    options?: MetabrowserAgeLabelOptions,
  ): string;
  countClass(value: number): "" | "count-large";
  /** What a change set's summary says, in a count summary's parts: "35 files changed · 2 A,
   *  3 D, 30 M · +1,234 −3,423", its file count and its brief change line, its text, and its
   *  words for a screen reader (docs/design-system.md, "Diff Summary"). */
  changeSummary(
    totals: {
      files: number | null;
      additions: number | null;
      deletions: number | null;
      exact: boolean;
    },
    entries: MetabrowserChangeLineInput["statuses"],
    formatCount: (count: number) => string,
  ): MetabrowserChangedFilesSummary;
  /** A brief change line, "10 A, 5 D, 4 M · +1,234 −567", from statuses and line totals, each
   *  count written with `formatCount` and an unknown one as "?": `text` as it reads, and
   *  `label` in words, "10 added, 5 deleted, 4 modified; 1,234 lines added, 567 deleted". A
   *  total of zero is left out; a change of no lines reads "0 lines". */
  changeLine(
    change: MetabrowserChangeLineInput,
    formatCount: (count: number) => string,
  ): MetabrowserChangeLine;
  /** A brief change line as nodes: its one `span.change-line`. */
  changeLineNodes(
    doc: Document,
    line: MetabrowserChangeLine,
    options?: MetabrowserChangeLineOptions,
  ): Array<Node | string>;
  /** A brief change line as markup. */
  changeLineHtml(line: MetabrowserChangeLine, options?: MetabrowserChangeLineOptions): string;
  /** A count summary as markup, each kind of part in its one class, the words escaped. */
  countPartsHtml(parts: MetabrowserCountParts): string;
  /** A count summary as nodes, each kind of part in its one class, the words as text. */
  countPartsNodes(doc: Document, parts: MetabrowserCountParts): Array<Node | string>;
  formatBytes(value: number): string;
  formatFileCount(value: number): string;
  formatInteger(value: number): string;
  /** A commit ID as a line names it, in the commit-ID face (`SHORT_COMMIT_CHARS`). */
  shortCommit(commit: string): string;
  sizeClass(value: number): "" | "size-large";
  /** A commit's or pull request's title as markup, its prefix in `span.title-prefix`. */
  titleHtml(title: string): string;
  /** A commit's or pull request's title as nodes, its prefix in `span.title-prefix`. */
  titleNodes(
    doc: Document,
    title: string,
    part?: (text: string, start: number) => Array<Node | string>,
  ): Array<Node | string>;
  /** A title's conventional-commit prefix and the rest after it, or null. */
  titlePrefix(title: string): { prefix: string; rest: string } | null;
}>;

type MetabrowserFileTypeCategoryId = string;

/** The shared icon registry (static/icons.js): each icon's SVG markup by name. */
type MetabrowserIconRegistry = Readonly<Record<string, string>> & {
  /**
   * The named icon with `cls` on its root `<svg>`, or "" for a name it does not hold.
   * Optional because a page without icons.js has an empty registry.
   */
  withClass?: (name: string | null | undefined, cls: string) => string;
};

type MetabrowserFileTypeCategory = Readonly<{
  id: MetabrowserFileTypeCategoryId;
  label: string;
  order: number;
  /**
   * The category's icon, which leads its heading wherever it is named, in the heading's
   * gray: its representative format's, and the shape every family in the group takes
   * unless it declares its own (file_type_filters.py, `_REPRESENTATIVE_FAMILIES`).
   */
  icon: string;
}>;

type MetabrowserFileTypeFamily = Readonly<{
  id: string;
  label: string;
  groupId: MetabrowserFileTypeCategoryId;
  /** Compatibility alias for groupId. */
  category: MetabrowserFileTypeCategoryId;
  order: number;
  extensions: ReadonlyArray<string>;
  /** The family's color, in oklch hue degrees; the theme supplies the rest. */
  hue: number;
  /** GitHub linguist language the hue came from, or null for a chosen hue. */
  linguist: string | null;
}>;

type MetabrowserFileTypeKind = Readonly<{
  id: string;
  familyId: string | null;
  groupId: MetabrowserFileTypeCategoryId;
  contentFamily: "code" | "prose" | "markup" | "data" | "binary" | "unknown";
  extensions: ReadonlyArray<string>;
  filenames: ReadonlyArray<string>;
  shebangs: ReadonlyArray<string>;
  priority: number;
}>;

type MetabrowserFileTypeClassification = Readonly<{
  logicalExtension: string | null;
  canonicalExtension: string | null;
  kindId: string | null;
  familyId: string | null;
  groupId: string;
  contentFamily: string;
  detectionSource: string;
  confidence: string;
  registryRevision: number;
  registryFingerprint: string;
}>;

type MetabrowserFileTypeFamilyMatch = Readonly<{
  family: MetabrowserFileTypeFamily;
  canonicalExtension: string;
}>;

type MetabrowserFileTypeTaxonomyRuntime = Readonly<{
  schema: "file-type-registry-v5";
  schemaVersion: 5;
  revision: number;
  fingerprint: string;
  maxExtensionComponents: 2;
  registryIdentity: Readonly<{
    schemaVersion: 5;
    revision: number;
    fingerprint: string;
  }>;
  groups: ReadonlyArray<MetabrowserFileTypeCategory>;
  /** The groups in the order the app lists them for a reader, Documentation first. */
  displayGroups: ReadonlyArray<MetabrowserFileTypeCategory>;
  families: ReadonlyArray<MetabrowserFileTypeFamily>;
  kinds: ReadonlyArray<MetabrowserFileTypeKind>;
  classify(name: unknown, extension: unknown): MetabrowserFileTypeClassification;
  matchExtension(extension: unknown): MetabrowserFileTypeFamilyMatch | null;
  canonicalExtension(extension: unknown): string;
  groupForFile(name: unknown, extension: unknown): MetabrowserFileTypeCategoryId;
  distributionKeyForExtension(extension: unknown): string;
  hueForDistributionKey(key: unknown): number | null;
  /** The icon a family paints with: its own, or its group's. */
  iconForFamily(familyId: unknown): string | null;
}>;

type MetabrowserInventoryWatch = Readonly<{
  dispose(): void;
  refresh(): Promise<void>;
  stale(): boolean;
}>;

type MetabrowserInventoryScopeRuntime = Readonly<{
  createInventoryWatch(
    scopePath: string,
    options: {
      active?: () => boolean;
      debounceMs?: number;
      fetch(signal: AbortSignal | undefined): Promise<unknown>;
      onError?(error: unknown): void;
    },
    onUpdate: (value: unknown) => void,
  ): MetabrowserInventoryWatch;
  pathsIntersectScope(changedPaths: unknown, scopePath: string): boolean;
}>;

type MetabrowserContributionRegistryRuntime = Readonly<{
  createContributionRegistry<T>(options: {
    compare(left: Readonly<T & { id: string }>, right: Readonly<T & { id: string }>): number;
    validate(id: string, spec: T): void;
  }): Readonly<{
    list(): ReadonlyArray<Readonly<T & { id: string }>>;
    register(id: string, spec: T): () => void;
  }>;
}>;

type MetabrowserResourceContextRuntime = Readonly<{
  createResourceContextStore<T>(options: {
    debounceMs: number;
    fetchEnvelope(path: string, signal: AbortSignal | undefined): Promise<T>;
    pathsIntersect(paths: unknown, path: string): boolean;
  }): Readonly<{
    dispose(): void;
    refresh(path: string): Promise<void>;
    seed(path: string, value: T): void;
    subscribe(path: string, listener: (value: T) => void): () => void;
  }>;
}>;

type MetabrowserSourceLineAnchorState = Readonly<{
  status: "none" | "shown" | "partial" | "not-loaded" | "past-end";
  start: number;
  end: number;
  message: string;
}>;

/** Navigation offered by the mounted GitHub PR page to its core tab host. */
type MetabrowserPullStackNavigation = Readonly<{
  hasStack(): boolean;
  moveStack(delta: -1 | 1): boolean;
}>;

type MetabrowserPullRouteRuntime = Readonly<{
  createPullPageHost<
    Handle extends {
      land?(route: { tab: string; file?: string }): void;
      setTab?(tab: string): void;
      showFile?(path: string): unknown;
      flush?(): void;
      ready?: Promise<void>;
      cancelPending?(): void;
      dispose?(): void;
    },
  >(deps: {
    claim(): number;
    isCurrent(claim: number): boolean;
    mount(
      claim: number,
      route: Readonly<MetabrowserPullRoute>,
      open: (route: MetabrowserPullRoute) => Promise<{ status: string }>,
    ): Promise<Handle | null | undefined>;
    mountList(claim: number): Promise<Handle | null | undefined>;
    pathname(): string;
    pushHref(href: string): void;
    replaceHref(href: string): void;
  }): Readonly<{
    dispose(): void;
    /** Cancel a visible page now, returning its final DOM disposal for actual handoff. */
    release(): (() => void) | null;
    onHistory(
      pathname: string,
      heldTarget: boolean,
    ): Readonly<
      | { action: "tab"; tab: string; file?: string }
      | { action: "mount"; number: number; tab: string; file?: string }
      | { action: "stack"; number: number; tab: string; file?: string }
      | { action: "list" }
    > | null;
    open(route: MetabrowserPullRoute): Promise<{ status: "opened" | "cancelled" }>;
    show(route: Readonly<MetabrowserPullRoute>): Promise<{ status: "opened" | "cancelled" }>;
    showList(): Promise<{ status: "opened" | "cancelled" }>;
    showStack(
      route: Readonly<{ number: number; tab: string; file?: string }>,
    ): Promise<{ status: "opened" | "cancelled" }>;
    /** The handle of the pull request's page holding the pane; null for the list or none. */
    page(): Handle | null;
    /** The page of that pull request when it holds the pane, else null. */
    pageFor(number: number): Handle | null;
    shown(): number | "list" | `stack:${number}` | null;
  }>;
  createViewMount(shell: {
    sdk: MetabrowserSdk;
    isCurrent(claim: number): boolean;
    renderHtml(html: string, claim: number): unknown;
    renderNode(node: HTMLElement, claim: number): unknown;
    beginNavigation(claim: number): boolean;
    endNavigation(claim: number): void;
    stageNode(node: HTMLElement, claim: number): (() => void) | null;
    showLoadFailure(claim: number, what: string): void;
  }): (
    claim: number,
    kind: string,
    context: Record<string, unknown>,
  ) => Promise<{
    setTab?(tab: string): void;
    flush?(): void;
    ready: Promise<void>;
    cancelPending?(): void;
    dispose(): void;
  } | null>;
  /** The host the shell made, for the Pulls tab beside the pane; null until one is made. */
  attachedHost(): { pageFor(number: number): unknown } | null;
  onPageChange(listener: () => void): () => void;
  parsePull(pathname: string): Readonly<{ number: number; tab: string; file: string }> | null;
  parsePulls(pathname: string, search?: string): Readonly<{ state: string }> | null;
  parseStack(
    pathname: string,
  ): Readonly<{ number: number; tab: string; file: string; stack: true }> | null;
  pullHistoryAction(
    pathname: string,
    shown: number | "list" | `stack:${number}` | null,
    heldTarget: boolean,
  ): Readonly<
    | { action: "tab"; tab: string; file?: string }
    | { action: "mount"; number: number; tab: string; file?: string }
    | { action: "stack"; number: number; tab: string; file?: string }
    | { action: "list" }
  > | null;
  pullHref(number: number, tab?: string, file?: string): string;
  pullsHref(state?: string): string;
  stackHref(number: number, tab?: string, file?: string): string;
}>;

type MetabrowserSourceLineAnchorsRuntime = Readonly<{
  countLines(text: string): number;
  describe(
    fragment: string | null | undefined,
    loaded: Readonly<{ lines: number; truncated: boolean }>,
  ): MetabrowserSourceLineAnchorState;
  gutterHtml(text: string): string;
  keyStep(
    current: string | null | undefined,
    focus: number,
    key: string,
    extend: boolean,
    layout: Readonly<{ lines: number; page: number; origin: number }>,
  ): Readonly<{ fragment: string; focus: number }> | null;
  lineAt(offsetY: number, lineHeight: number, lines: number): number;
  mount(
    host: ParentNode,
    options: {
      path: string;
      truncated: boolean;
      navigation: Readonly<{
        current(): MetabrowserNavigationTarget | null;
        open(target: MetabrowserNavigationTarget, options: { replace: boolean }): Promise<void>;
      }> | null;
    },
  ): void;
  nextFragment(current: string | null | undefined, line: number, extend: boolean): string;
  normalizeLineEndings(text: string, afterCarriageReturn?: boolean): string;
  parse(fragment: string | null | undefined): Readonly<{ start: number; end: number }> | null;
  preferredView(target: MetabrowserNavigationTarget | null | undefined): "source" | null;
  refresh(root: ParentNode, loaded: { content_truncated?: boolean }): void;
  spoken(state: MetabrowserSourceLineAnchorState): string;
}>;

type MetabrowserSourceAppendRuntime = Readonly<{
  TEXT_NODE_MAX_LENGTH: number;
  appendSourceText(root: ParentNode | null, text: string, before?: string): boolean;
  commitChunkCache(options: {
    cached: Record<string, unknown>;
    cachedForPath: Record<string, unknown> | undefined;
    claim: number | null;
    commit(nextCached: Record<string, unknown>): void;
    currentPath: string | null;
    isClaimCurrent(claim: number): boolean;
    nextCached: Record<string, unknown>;
    path: string;
    requested: number;
    requestCap: number;
  }): number | null;
  nextCacheValue(
    cached: Record<string, unknown>,
    chunk: Record<string, unknown>,
  ): Record<string, unknown>;
  nextChunkBytes(current: number, cap: number): number;
  requestOwnsPreview(options: {
    cached: Record<string, unknown>;
    cachedForPath: Record<string, unknown> | undefined;
    claim: number | null;
    currentPath: string | null;
    isClaimCurrent(claim: number): boolean;
    path: string;
  }): boolean;
  syncLoadMoreFooter(root: ParentNode | null, markup: string): boolean;
  syncTruncationWarning(root: ParentNode | null, markup: string): boolean;
  textPieces(text: string, limit?: number): string[];
}>;

type MetabrowserViewStateRuntime = Readonly<{
  isActive(container: HTMLElement): boolean;
  setActive(container: HTMLElement, active: boolean): void;
  setPrintState(
    container: HTMLElement,
    state: { printable: boolean; profile?: string; runtime?: string },
  ): void;
  subscribeActive(container: HTMLElement, listener: (active: boolean) => void): () => void;
}>;

type MetabrowserPerf = {
  copy?(): unknown;
  download?(): unknown;
  measure<T>(name: string, fn: () => T, metadata?: Record<string, unknown>): T;
  measureAsync<T>(
    name: string,
    fn: () => Promise<T>,
    metadata?: Record<string, unknown>,
  ): Promise<T>;
  report?(): unknown;
  reset?(): void;
  /**
   * How responsive the page has been since load: the worst main-thread block,
   * the same for the first five seconds alone, the blocked share with the
   * window it is a share of, and interaction-to-next-paint percentiles.
   *
   * `measurement_valid` is false when the tab was ever hidden, because browser
   * throttling makes that scheduling incomparable to a visible session.
   */
  responsiveness?(): MetabrowserResponsiveness;
  setSlowThreshold?(milliseconds: number): number;
  snapshot?(): unknown;
};

type MetabrowserDebug = Readonly<{
  clearFileCache(path?: string): void;
  selectFile(path: string): Promise<unknown>;
}>;

type MetabrowserBench = Readonly<{
  run(options?: { clients?: number; shapes?: Record<string, string> }): Promise<string>;
  SHAPES: Record<string, string>;
}>;

type MetabrowserResponsiveness = {
  animation_frame_blocking_ms_max: number | null;
  animation_frame_blocking_ms_total: number | null;
  animation_frame_max_ms: number | null;
  animation_frames: number | null;
  animation_frames_over_200ms: number | null;
  attribution_unsupported: string[] | null;
  ever_hidden: boolean;
  forced_style_layout_ms_max: number | null;
  interaction_max_ms: number | null;
  interaction_inputs: number;
  interaction_p50_ms: number | null;
  interaction_p95_ms: number | null;
  interaction_percentile_scope: string;
  interaction_samples_retained: number;
  interactions: number;
  long_task_max_ms: number;
  long_task_max_ms_first_5s: number;
  long_task_ms_total: number;
  long_tasks: number;
  long_tasks_over_200ms: number;
  main_thread_blocked_pct: number | null;
  measurement_valid: boolean;
  profile_started_at_ms: number;
  total_blocking_time_ms: number;
  unsupported: string[] | null;
  visibility_state: string | null;
  window_ms: number;
};

type MetabrowserChartRuntime = {
  dispose(container: HTMLElement): void;
  renderPayload(container: HTMLElement, chartData: MetabrowserPluginData): unknown;
};

type MetabrowserChartInstance = {
  data: Record<string, unknown>;
  destroy(): void;
  options: Record<string, unknown>;
  update(mode?: string): void;
};

type MetabrowserThemeChange = {
  mode: "dark" | "light" | "system";
  resolved: "dark" | "light";
};

/** static/nav-collapse.js: hiding and showing the navigation pane. */
type MetabrowserNavCollapseController = Readonly<{
  button: HTMLButtonElement;
  isCollapsed(): boolean;
  setCollapsed(collapsed: boolean): void;
  toggle(): void;
  subscribe(listener: () => void): () => void;
  dispose(): void;
}>;

type MetabrowserNavCollapseRuntime = Readonly<{
  create(options: {
    button: HTMLButtonElement;
    container: HTMLElement;
    document?: Document;
    focusFallback?: () => HTMLElement | null;
    frame: HTMLElement;
    onHide?: () => void;
    pane: HTMLElement;
    reducedMotion?: () => boolean;
  }): MetabrowserNavCollapseController;
}>;

/** static/revision-ages.js: the watch on a Git revision's file ages while they are read. */
type MetabrowserRevisionAgesState = { state: string };

/** The `ages` a response carries: the state of the read of a revision's file times. */
type MetabrowserRevisionAgesStatus = {
  state?: string;
  reason?: string;
  files?: number;
  dated?: number;
  older_than?: number | null;
  stop?: string;
};

type MetabrowserRevisionAgesController = Readonly<{
  observe(ages: { state?: string } | null | undefined): void;
  stop(): void;
  isWatching(): boolean;
}>;

type MetabrowserRevisionAgesRuntime = Readonly<{
  annotate(): void;
  createController(deps: {
    fetchState: () => Promise<MetabrowserRevisionAgesState | null>;
    landed: (state: MetabrowserRevisionAgesState) => void;
    setTimer: (run: () => void, ms: number) => unknown;
    clearTimer: (timer: unknown) => void;
    now: () => number;
    pollMs: number;
    giveUpMs?: number;
  }): MetabrowserRevisionAgesController;
  mount(options: {
    reload: (state: MetabrowserRevisionAgesState) => void;
    pollMs?: number;
    giveUpMs?: number;
  }): MetabrowserRevisionAgesController;
  noteText(
    ages: MetabrowserRevisionAgesStatus | null | undefined,
    undated?: number | null,
  ): string | null;
  track(ages: MetabrowserRevisionAgesStatus | null | undefined, undated?: number | null): void;
}>;

type MetabrowserThemeRuntime = {
  notifyChanged(detail: MetabrowserThemeChange): void;
  subscribe(listener: (detail: MetabrowserThemeChange) => void): () => void;
};

type MetabrowserFilterOption = {
  ageClass?: string;
  className?: string;
  count?: number;
  icon?: string;
  iconClass?: string;
  /** In a dropdown, the letter that chooses this row while the menu is open and has focus. */
  key?: string;
  label: string;
  /** The chip's tooltip, its `data-tip-text` (`ChipOption` in filter-controls.js). */
  tip?: string;
  title?: string;
  value: string;
};

type MetabrowserFilterSelection = string | Array<string> | null;

type MetabrowserFilterSnapshot = {
  group?: string;
  recency: string;
  showIgnored: boolean;
  size: string;
  types: Array<string> | null;
};

/** One section of a grouped tree (tree-filter-model.js, groupSections). */
type MetabrowserTreeSection = {
  /** Null where the source could not count the group (a truncated Git index). */
  files: number | null;
  /** A type group's category icon, a name in the icon registry; null by age. */
  icon: string | null;
  id: string;
  /** `<by>:<id>`, the group a folder inside it opens under. */
  key: string;
  label: string;
  size: number | null;
  tree: Array<Record<string, unknown>>;
};

type MetabrowserFilterState = {
  activeCount(): number;
  clear(): void;
  get(): MetabrowserFilterSnapshot;
  set(patch: Partial<MetabrowserFilterSnapshot>): void;
  subscribe(listener: (snapshot: MetabrowserFilterSnapshot) => void): () => void;
};

type MetabrowserFilterHandlers = {
  onChange?: (key: string, value: string, select: string) => void;
  onClear?: () => void;
  onMenuFocus?: (key: string, value: string | null) => void;
  onMenuPick?: (key: string, value: string | null) => void;
  onMenuPreset?: (key: string, presetId: string, wasOn: boolean) => void;
  onMenuToggle?: (key: string, open: boolean) => void;
  onToggle?: (key: string, pressed: boolean) => void;
};

type MetabrowserFilterPreset = {
  count?: number;
  id: string;
  label: string;
  values: Array<string>;
};

/** One File type tally row: `[key, tracked, ignored]`, as /api/rollup and /api/tree send. */
type MetabrowserTypeTallyRow = Readonly<[string, number, number]>;

/** The File type counts a menu is built from (a comparison's `view=types` answer too). */
type MetabrowserTypeTally = Readonly<{
  extensions?: ReadonlyArray<MetabrowserTypeTallyRow>;
  canonical_extensions?: ReadonlyArray<MetabrowserTypeTallyRow>;
  type_families?: ReadonlyArray<MetabrowserTypeTallyRow>;
  type_presets?: ReadonlyArray<MetabrowserTypeTallyRow>;
}>;

type MetabrowserTypeMenuOptions = {
  /** Count the gitignored column too; true unless said otherwise. */
  showIgnored?: boolean;
  /** At most this many extension rows; `typeMenu.MAX_OPTIONS` unless said otherwise. */
  max?: number;
  /** A row's icon for a file name; the shell's `MetabrowserFileTypes.iconFor` by default. */
  iconFor?: (name: string) => { svg: string; cls: string };
  /** A group heading's icon; the icon registry's `withClass` by default. */
  groupIcon?: (name: string, cls: string) => string;
};

type MetabrowserTypePresetSection = {
  id: string;
  label?: string;
  icon?: string;
  presets: Array<MetabrowserFilterPreset>;
};

/** The File type menu's rows, shared by the Files tab and a diff's toolbar. */
type MetabrowserTypeMenu = Readonly<{
  MAX_OPTIONS: number;
  options(
    tally: MetabrowserTypeTally,
    options?: MetabrowserTypeMenuOptions,
  ): Array<MetabrowserFilterOption>;
  presetSections(
    tally: MetabrowserTypeTally,
    options?: MetabrowserTypeMenuOptions,
  ): Array<MetabrowserTypePresetSection>;
  /** The selection after a preset row is pressed: its values added, or removed when it was on. */
  togglePreset(
    current: ReadonlyArray<string> | null,
    values: ReadonlyArray<string>,
    wasOn: boolean,
  ): Array<string> | null;
}>;

type MetabrowserFilterControls = {
  /** Choose a dropdown row as a click on it does; false when no bound container holds it. */
  activateMenuRow(row: HTMLElement): boolean;
  /** The File type menu's rows, built from a tally. */
  typeMenu: MetabrowserTypeMenu;
  /** Wire one control's element. It answers for every dropdown inside `root`, so bind no
   * region that holds another bound control: it would take that control's open dropdown. */
  bind(root: Element, handlers: MetabrowserFilterHandlers): () => void;
  checkHtml(spec: {
    checked?: boolean;
    className?: string;
    key: string;
    label: string;
    tip?: string;
  }): string;
  clearHtml(spec?: { className?: string; label?: string }): string;
  escapeHtml(value: unknown): string;
  fitJoinedGroups(root: Element): void;
  fitOpenMenus(root: Element): void;
  /** Focus an open dropdown's checked row, or else its first; null when it is not open. */
  focusMenu(root: Element, key: string): HTMLElement | null;
  groupHtml(spec: {
    className?: string;
    key: string;
    label: string;
    layout?: "joined" | "wrap";
    options: Array<MetabrowserFilterOption>;
    select?: string;
    value: MetabrowserFilterSelection;
  }): string;
  isSelected(current: MetabrowserFilterSelection, value: string): boolean;
  joinedGroupFits(widths: { joined: number; room: number }): boolean;
  /**
   * Call before rebuilding `root`'s markup, and the returned function after: focus goes
   * back to the control that had it, or to the trigger of a menu the rebuild closed.
   */
  keepFocus(root: Element): () => void;
  menuGroupHtml(spec: {
    /** The any-row's letter, as an option's `key` is its row's. */
    anyKey?: string;
    anyLabel: string;
    anyValue?: string;
    key: string;
    label: string;
    menuId: string;
    open?: boolean;
    options: Array<MetabrowserFilterOption>;
    presets?: Array<MetabrowserFilterPreset>;
    presetSections?: Array<{
      id: string;
      label?: string;
      /** A category's icon, as markup from the icon registry, which leads its heading. */
      icon?: string;
      presets: Array<MetabrowserFilterPreset>;
    }>;
    select?: string;
    value: MetabrowserFilterSelection;
  }): string;
  menuMaxHeight(geometry: {
    frame: number;
    rowHeight: number;
    top: number;
    windowHeight: number;
  }): number;
  nextSelection(
    select: string,
    current: MetabrowserFilterSelection,
    value: string,
  ): MetabrowserFilterSelection;
  toggleHtml(spec: {
    ariaLabel?: string;
    badge?: number;
    className?: string;
    controls?: string;
    icon?: string;
    key: string;
    label?: string;
    pressed?: boolean;
    /** The tooltip, as `data-tip-text`; filter-controls.js reads `tip`, never `title`. */
    tip?: string;
  }): string;
};

type MetabrowserPluginData = {
  parse_error?: unknown;
  parsed?: unknown;
  pretty_yaml?: string;
  sizeBytes?: number;
  truncated?: unknown;
  [key: string]: unknown;
};

/**
 * A row of the structured tree (structured/tree.js `materializeRows`). Its path is
 * positional ("$/3/0"). Internal to Metabrowser's own views: `renderInlineTree` is the
 * stable embedding contract, and a row's fields change with the views that draw them.
 */
type StructuredTreeRow = {
  path: string;
  level: number;
  /** "kv", "item", "open", "empty", or "more" for the children a page leaves out. */
  kind: string;
  key: string | null;
  value?: unknown;
  isArrayIndex: boolean;
  isArray?: boolean;
  childCount?: number;
  expanded?: boolean;
  /** How a rendered diff marks the row; the file view sets none. */
  change?: "context" | "modified" | "added" | "removed";
  /** A number's JSON text, drawn in place of its value (a diff answer's entry `text`). */
  text?: string;
  /** A "more" row's count of children left out. */
  hidden?: number;
  /** A "more" row's count of changed entries among those left out (a rendered diff). */
  changed?: number;
};

/** Where `materializeRows` places a value and how many children an open container draws. */
type StructuredMaterializeOptions = {
  path?: string;
  level?: number;
  key?: string | null;
  isArrayIndex?: boolean;
  limit?: number;
  shown?: ReadonlyMap<string, number>;
};

/** The file view's first-draw expansion (structured/tree.js `EXPANSION`). */
type StructuredExpansion = Readonly<{
  maxLines: number;
  maxExpandThreshold: number;
  indentChars: number;
}>;

type StructuredExports = {
  calculateOptimalExpansion: (
    parsed: unknown,
    options: { maxLines?: number; maxExpandThreshold?: number; indentChars?: number },
  ) => Set<string>;
  expansion: StructuredExpansion;
  formatValue: (...args: Array<unknown>) => unknown;
  generateStructuredPreview: (...args: Array<unknown>) => unknown;
  materializeRows: (
    parsed: unknown,
    expandedPaths: ReadonlySet<string>,
    options?: StructuredMaterializeOptions,
  ) => StructuredTreeRow[];
  renderRowHtml: (row: StructuredTreeRow, indentChars: number) => string;
  renderInlineTree(
    container: HTMLElement,
    data: unknown,
    options?: Record<string, unknown>,
  ): DisposableHandle | undefined;
  renderSource: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  renderTree: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
};

/** agent-log.js's exports, which the agents plugin's `loadLogRenderers` answers. */
type AgentLogRenderers = {
  disposeCharts: (container?: HTMLElement) => void;
  disposeLog: (container?: HTMLElement) => void;
  renderCharts: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  renderLog: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  renderLogEvent: (container: HTMLElement, event: unknown, index: number) => string;
  renderRaw: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
};

type AgentsExports = {
  /** The agent-log renderers and their stylesheet, loaded on demand, once. */
  loadLogRenderers: () => Promise<AgentLogRenderers>;
};

/** A file card's disclosure, as the diff view's `fileDisclosure` makes one: its `bar`,
 * empty, and its `toggle`, the button that holds the chevron, for the caller to name the
 * file in and place first on the bar; and the card's state, open at first. The one shape
 * of it: the diff view returns it, and a plugin that requires the diff plugin takes it
 * from `guidePatchDrawer().disclose(section, folded, changed)`, whose optional `changed`
 * hears each fold and opening, after it is drawn, with whether the card is now open; a
 * page that keeps a reader's folds keeps them from it. */
type DiffFileDisclosureShape = {
  bar: HTMLElement;
  toggle: HTMLButtonElement;
  expanded(): boolean;
  setExpanded(next: boolean): void;
};

/** What the diff plugin exports to a plugin that requires it. */
type DiffExports = {
  loadFullSource: typeof import("../builtin_plugins/diff/index.js").loadFullSource;
  guidePatchDrawer: () => ReturnType<
    typeof import("../builtin_plugins/diff/index.js").guidePatchDrawer
  >;
  /** One file's hunks, as the diff route answers them, drawn as Changes draws a file's
   * body: each hunk under its header bar, long changed runs behind fold bars, then changed
   * runs paired and syntax colored. Unified only. `dispose` stops what is still to come. */
  mountFilePatch: (
    body: HTMLElement,
    change: Record<string, unknown>,
    patch: Record<string, unknown>,
    api: MetabrowserPublicSdk,
  ) => { dispose(): void };
  /** One changed file of a comparison drawn whole from the comparison route's one-file
   * answer by the diff view's own `render`, rendered layer included, *ctx* as a host passes
   * that view. `settled` is true once the file is drawn, and false when it is not: the
   * view's notice then says why in its place, or the handle was disposed first. `dispose`
   * ends the read on its way or removes what was drawn. */
  mountRenderedFile: (
    container: HTMLElement,
    comparison: NonNullable<MetabrowserRenderContext["comparison"]>,
    path: string,
    ctx?: MetabrowserRenderContext,
  ) => {
    settled: Promise<boolean>;
    show(mode: "diff" | "current" | "full"): void;
    dispose(): void;
  };
};

/** What the GitHub plugin exports for the shell. */
type GithubExports = {
  /** A pull request's state as the Pulls tab draws it: its icon, named for assistive
   * technology unless `named` is false. */
  pullStateIcon: (
    state: "open" | "draft" | "merged" | "closed",
    options?: { named?: boolean },
  ) => HTMLElement;
};

type MarkdownExports = {
  mountRendered: (
    container: HTMLElement,
    ctx: MetabrowserRenderContext,
    /** `includeToc` is the render route's `toc` query: omitted leaves the decision to
     * KPress's own thresholds, and no built-in caller sets it (mb-2nqa tracks its
     * removal). `pagePath` is the path of the page that shows the document as its own
     * when that is not the document's, as a folder's Overview shows its README, with its
     * table of contents: the document's fragments are places on that page.
     * `printIndicator: true` puts a print button in the corner of the document's
     * card, for a host whose view prints the document itself; it is off unless asked. */
    options?: {
      signal?: AbortSignal;
      includeToc?: "auto" | "on" | "off";
      pagePath?: string;
      printIndicator?: boolean;
    },
  ) => DisposableHandle;
  renderSource: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  /** Draw the Mermaid diagrams in a placed KPress render under *root*: images unless
   * `inert: false` says the render is trusted, laid out in a frame whose policy loads
   * nothing when `isolated: true` says nothing else bounds them. Null when *root* holds
   * no diagram, so nothing is fetched; otherwise `dispose` stops drawing and leaves the
   * figures. */
  drawDiagrams: (
    root: ParentNode,
    options?: { inert?: boolean; isolated?: boolean },
  ) => { dispose(): void; ready: Promise<void> } | null;
};

/** A provider plugin's exports, the namespace of its index.js, by the plugin's name. */
type MetabrowserPluginExports = {
  agents: AgentsExports;
  diff: DiffExports;
  github: GithubExports;
  markdown: MarkdownExports;
  structured: StructuredExports;
};

/** One plugin's assets, as the server's plugin table (`_build_plugin_asset_config_block`) names them. */
type PluginAssets = Readonly<{
  name: string;
  module: string;
  scripts: string[];
  styles: string[];
}>;

/** `metabrowser.plugins`: a plugin's declared providers ("Declared Dependencies"). */
type MetabrowserPlugins = Readonly<{
  load<Name extends keyof MetabrowserPluginExports>(
    name: Name,
  ): Promise<MetabrowserPluginExports[Name]>;
  load(name: string): Promise<object>;
}>;

type MetabrowserRollupEnvelope = {
  root: string;
  path: string;
  /** Present only when the body is in the compact encoding. */
  encoding?: "compact";
  node: Record<string, unknown> | null;
  ext_tallies: Array<Array<unknown>>;
  file_type_breakdown: MetabrowserFileTypeBreakdown | null;
  /** File Overview's compact legend; null exactly when `file_type_breakdown` is. */
  file_type_legend: MetabrowserFileTypeLegend | null;
  index_status: string;
  indexed_files: number;
  max_files: number;
  truncated: boolean;
};

type MetabrowserFileTypeMeasure = {
  files: number;
  bytes: number;
  [metric: string]: number;
};

type MetabrowserFileTypeMetrics = Record<string, MetabrowserFileTypeMeasure>;

type MetabrowserFileTypeBreakdown = {
  schema: "file-type-breakdown-v1";
  registry: { schema_version: 1; revision: number; fingerprint: string };
  metrics: MetabrowserFileTypeMetrics;
  groups: Array<{
    id: string;
    families: Array<{
      id: string;
      metrics: MetabrowserFileTypeMetrics;
      extensions: Array<{ extension: string; metrics: MetabrowserFileTypeMetrics }>;
    }>;
  }>;
  no_extension: {
    metrics: MetabrowserFileTypeMetrics;
    filenames: Array<{ basename: string; metrics: MetabrowserFileTypeMetrics }>;
    others: {
      metrics: MetabrowserFileTypeMetrics;
      omitted_distinct_values: number;
    } | null;
  };
  remaining_types: {
    metrics: MetabrowserFileTypeMetrics;
    extensions: Array<{ extension: string; metrics: MetabrowserFileTypeMetrics }>;
    others: {
      metrics: MetabrowserFileTypeMetrics;
      omitted_distinct_values: number;
    } | null;
  };
};

/** The legend for one measure in one population: named families, then the rest. */
type MetabrowserFileTypeLegendView = {
  total: number;
  named: Array<{ family: string; value: number }>;
  other: number;
};

type MetabrowserFileTypeLegend = {
  schema: "file-type-legend-v1";
  limit: number;
  minimum_share_percent: number;
  files: { all: MetabrowserFileTypeLegendView; unignored: MetabrowserFileTypeLegendView };
  bytes: { all: MetabrowserFileTypeLegendView; unignored: MetabrowserFileTypeLegendView };
};

type MetabrowserRollupOptions = {
  active?: () => boolean;
  debounceMs?: number;
  depth?: number | "max";
  /** `compact` writes each expanded folder's files as positional `files` entries
   * (`RollupCompactFile` in wire_models.py); the SDK returns the body undecoded. */
  encoding?: "json" | "compact";
  ext_rank?: "bytes" | "dual";
  ext_top?: number;
  filename_top?: number;
  /** `exclude` leaves gitignored entries out of children and the node budget. */
  ignored?: "include" | "exclude";
  /** The node budget: a positive integer, or `max` for `ROLLUP_MAX_NODES`. */
  nodes?: number | "max";
  onError?: (error: unknown) => void;
  remaining_top?: number;
  signal?: AbortSignal;
  top?: number | "max";
};

type MetabrowserRollupWatch = {
  refresh(): Promise<void>;
  stale(): boolean;
  dispose(): void;
};

type MetabrowserFolderEnvelope = {
  dir: {
    gitignored: boolean;
    mtime: number | null;
    not_indexed?: "hidden" | "symlink";
    state: "pending" | "complete";
    total_files: number | null;
    total_size: number | null;
    unignored_files: number | null;
    unignored_size: number | null;
  };
  kind: "folder";
  name: string;
  path: string;
  readme_path: string;
  readme_search_truncated?: boolean;
  type: "folder";
  views: Array<Record<string, unknown>>;
};

type FolderOverviewPanelPlacement = "summary" | "content" | "supplemental";
type FolderOverviewPanelPresentation = "surface" | "document";
type FolderOverviewPanelError = Readonly<{ message: string; retryable: boolean }>;
type FolderOverviewResolution<T> = Readonly<{ data: T; key: string }> | null;
type FolderOverviewMountHandle<T> = Readonly<{
  dispose(): void;
  update?(context: MetabrowserRenderContext, data: T): void | Promise<void>;
}>;
type FolderOverviewPanelSpec<T> = Readonly<{
  collapsible?: boolean;
  classifyError?(error: unknown): FolderOverviewPanelError;
  label: string;
  defaultExpanded?: boolean;
  mount(
    container: HTMLElement,
    context: MetabrowserRenderContext,
    data: T,
    options: { signal?: AbortSignal },
  ): undefined | FolderOverviewMountHandle<T> | Promise<undefined | FolderOverviewMountHandle<T>>;
  placement: FolderOverviewPanelPlacement;
  presentation: FolderOverviewPanelPresentation;
  printable?: boolean;
  required?: boolean;
  resolve(
    context: MetabrowserRenderContext,
    options: { signal: AbortSignal },
  ): FolderOverviewResolution<T> | Promise<FolderOverviewResolution<T>>;
}>;
type FolderOverviewPanelDescriptor<T> = Readonly<FolderOverviewPanelSpec<T> & { id: string }>;
type FolderOverviewRegistry = Readonly<{
  listPanels(): ReadonlyArray<FolderOverviewPanelDescriptor<unknown>>;
  registerPanel<T>(id: string, spec: FolderOverviewPanelSpec<T>): () => void;
}>;

type MetabrowserDirectoryTotals = Readonly<{
  path: string;
  revision: number;
  state: "pending" | "complete";
  totalFiles: number;
  totalBytes: number;
  unignoredFiles: number;
  unignoredBytes: number;
}>;

type MetabrowserDirectoryTotalsStore = Readonly<{
  get(path: string): MetabrowserDirectoryTotals | null;
  subscribe(path: string, listener: (value: MetabrowserDirectoryTotals | null) => void): () => void;
}>;

type MetabrowserDirectoryTotalsHostStore = MetabrowserDirectoryTotalsStore &
  Readonly<{
    applyChange(ops: ReadonlyArray<Record<string, unknown>>): void;
    applySnapshot(entries: ReadonlyArray<unknown>): void;
  }>;

type MetabrowserFileTypeIcon = Readonly<{
  className: string;
  svg: string;
}>;

type MetabrowserTreemapCell = {
  kind: string;
  name: string;
  path: string;
  x: number;
  y: number;
  w: number;
  h: number;
  depth: number;
  value: number;
  mtime?: number;
  ext?: string;
  gitignored?: boolean;
  state?: string;
  nested?: boolean;
  files?: number;
  bytes?: number;
};

type MetabrowserTreemapWeightedItem = { value: number } & Record<string, unknown>;

type MetabrowserTreemapLayoutApi = {
  LAYOUT_DEFAULTS: Record<string, number>;
  squarify(
    items: Array<MetabrowserTreemapWeightedItem>,
    rect: { x: number; y: number; w: number; h: number },
  ): Array<{ item: MetabrowserTreemapWeightedItem; x: number; y: number; w: number; h: number }>;
  layoutTree(
    rootNode: Record<string, unknown>,
    viewport: { w: number; h: number },
    options: Record<string, unknown>,
  ): Array<MetabrowserTreemapCell>;
  worstAspect(areas: Array<number>, side: number): number;
};

type MetabrowserSdk = {
  ageBucket(mtimeSeconds: number | null | undefined): MetabrowserAgeBucket | null;
  /** An age as every surface draws one (`MetabrowserFormatters.ageLabel`): its label in its
   *  freshness class, after `options.className`, which places it. */
  ageLabel(
    secondsSinceEpoch: number | null | undefined,
    options?: MetabrowserAgeLabelOptions,
  ): HTMLSpanElement;
  ageLabelHtml(
    secondsSinceEpoch: number | null | undefined,
    options?: MetabrowserAgeLabelOptions,
  ): string;
  /** Tell a drawn age as of now, its freshness class swapped in place; returns its label. */
  retellAge(
    element: Element,
    secondsSinceEpoch: number | null | undefined,
    options?: MetabrowserAgeOptions,
  ): string;
  bench?: MetabrowserBench;
  debug?: MetabrowserDebug;
  errors: MetabrowserRequestErrorRuntime;
  /** What the page reports to the event log, and its Details panel (static/event-reports.js). */
  eventReports?: MetabrowserEventReports;
  directoryTotals: MetabrowserDirectoryTotalsStore;
  filters: MetabrowserFilterState;
  plugins: MetabrowserPlugins;
  folderOverview?: FolderOverviewRegistry;
  folderContext: Readonly<{
    refresh(path: string): Promise<void>;
    seed(path: string, value: MetabrowserFolderEnvelope): void;
    subscribe(path: string, listener: (value: MetabrowserFolderEnvelope) => void): () => void;
  }>;
  chart(
    container: HTMLElement | HTMLCanvasElement,
    type: string,
    data: Record<string, unknown>,
    options?: Record<string, unknown>,
  ): MetabrowserChartInstance;
  escapeHtml(value: string): string;
  fetchRollup(path: string, opts?: MetabrowserRollupOptions): Promise<MetabrowserRollupEnvelope>;
  fetchCompleteText(
    ctx: MetabrowserRenderContext,
    options?: { signal?: AbortSignal },
  ): Promise<string>;
  fetchText(
    target: MetabrowserNavigationTarget,
    options?: { signal?: AbortSignal },
  ): Promise<string>;
  fileCatalog: MetabrowserPublicFileCatalogApi;
  fileTypes: MetabrowserFileTypeTaxonomyRuntime;
  fileTypeClass(path: string): string;
  fileTypeIcon(path: string): MetabrowserFileTypeIcon;
  refChipHtml(name: string, options?: MetabrowserRefChipOptions): string;
  refChip(name: string, options?: MetabrowserRefChipOptions): HTMLElement;
  /** A merge as source → target: two ref chips and the one shared arrow, left to right. */
  mergeRefs(
    source: { name: string } & MetabrowserRefChipOptions,
    target: { name: string } & MetabrowserRefChipOptions,
    options?: MetabrowserRefChipOptions,
  ): HTMLElement;
  mountRefMenus(primary: HTMLElement, host: HTMLElement): () => void;
  /** Same overlay and disposal contract as mountRefMenus. */
  mountRefCopies(primary: HTMLElement, host: HTMLElement): () => void;
  /** A person, as every page draws one: an avatar's box, `--actor-avatar-size` square from
   *  first paint, then the bold name in `.actor-name`. The box holds the avatar where
   *  `avatar` is an https address the caller vouches for, and the shell's person glyph
   *  where it is not or the image fails; `placeholder: false` draws no box without one
   *  (docs/design-system.md, "Actor Identity"). */
  actorIdentity(name: string, options?: MetabrowserActorIdentityOptions): HTMLElement;
  /** The same identity as markup, its box holding the person glyph. */
  actorIdentityHtml(
    name: string,
    options?: Pick<MetabrowserActorIdentityOptions, "className" | "nameClass">,
  ): string;
  /** A page's external counterpart as a split button: its link, and a menu of Copy Link
   *  and Open in Browser (docs/design-system.md, "View on GitHub"). */
  counterpartButton(counterpart: MetabrowserCounterpart): HTMLElement;
  /** Copy Link and Open in Browser rows for a trusted HTTP or HTTPS URL. */
  externalLinkMenuItems(
    url: string,
    options?: {
      onActivate?: () => void;
      onCopyResult?: (result: "copied" | "failed") => void;
    },
  ): [HTMLButtonElement, HTMLAnchorElement];
  /** Ask `GET /api/counterpart` for `page`'s counterpart and put its button in `corner`,
   *  a header's `.view-header-end`; resolves to the button, or null when there is none. */
  mountCounterpart(corner: Element, page: string): Promise<HTMLElement | null>;
  /** Start asking for `page`'s counterpart before its header is drawn; `mountCounterpart`
   *  waits for this request rather than making another. */
  prefetchCounterpart(page: string): void;
  /** View-phase destination mark; a state icon may come only from trusted view metadata. */
  decorateExternalLink<T extends HTMLElement>(
    anchor: T,
    options?: { icon?: Element | "github"; position?: "before" | "after" },
  ): T;
  /** An age in words, for a sentence or an accessible name; a drawn age is `ageLabel`'s. */
  formatAge(
    secondsSinceEpoch: number,
    options?: MetabrowserAgeOptions,
  ): { label: string; className: string };
  formatTimestamp(secondsSinceEpoch: number): string;
  /** A commit's or pull request's title as nodes for its element: a conventional-commit
   *  prefix in `span.title-prefix`, at regular weight, then the rest. */
  titleNodes(title: string): Array<Node | string>;
  /** A commit ID as every line names one (`MetabrowserFormatters.shortCommit`), for an
   *  element of class `git-commit-sha`, the commit-ID face. */
  shortCommit(commit: string): string;
  /** A count summary as nodes for its element, painted as the shell paints every count
   *  summary: each count in `span.summary-number`, byte values in the shared size style,
   *  each mark in `span.summary-punctuation`,
   *  a separator hidden from assistive technology and its `spoken` in `span.visually-hidden`,
   *  each status count, "21 A", its number and letter in one
   *  `span.summary-status-count.file-change-status`, bold in its status's ink, and the words
   *  as text. */
  countPartsNodes(parts: MetabrowserCountParts): Array<Node | string>;
  /** A brief change line, "10 A, 5 D, 4 M · +1,234 −567", from a change set's statuses and
   *  line totals, in the shell's number format: the one component for one
   *  (docs/design-system.md, "Brief Change Line"). */
  changeLine(change: MetabrowserChangeLineInput): MetabrowserChangeLine;
  /** A brief change line as nodes for its element, painted as the shell paints every one: its
   *  one `span.change-line`. */
  changeLineNodes(
    line: MetabrowserChangeLine,
    options?: MetabrowserChangeLineOptions,
  ): Array<Node | string>;
  /** A change set's size line, "77 commits · 83 files changed · 2.3 MB compressed (14.0 MB raw
   *  diff)", in the shell's number and size formats: the one component for one
   *  (docs/design-system.md, "Change Size Line"). */
  changeSizeLine(change: MetabrowserChangeSizeInput): MetabrowserChangeSizeLine;
  /** A change set's size line as nodes for its element: its one `span.change-size-line`, the
   *  size in `span.change-size-line-size` with a tooltip saying what each size is. */
  changeSizeLineNodes(line: MetabrowserChangeSizeLine): Array<Node | string>;
  /** A change set's size line as markup, for a view that writes markup as text. */
  changeSizeLineHtml(line: MetabrowserChangeSizeLine): string;
  prefs: {
    get<T>(name: string, fallback: T): T;
    set(name: string, value: unknown): boolean;
  };
  tooltip: {
    /** Put the tooltip away. With `within`, a tooltip anchored at or inside it, or one
     *  whose anchor has left the document, and never one shown with no anchor. With
     *  none, any tooltip but one anchored in the nav's header. See
     *  docs/design-system.md, "A Surface Puts Away Only Its Own Tooltip". */
    hide(within?: Element | null): void;
    /** Show `html` anchored to the element it describes. No move(): a tooltip
     *  holds still once shown; see docs/design-system.md. */
    show(html: string, anchor: Element | null): void;
  };
  watchRollup(
    path: string,
    opts: MetabrowserRollupOptions,
    onUpdate: (envelope: MetabrowserRollupEnvelope) => void,
  ): MetabrowserRollupWatch;
  onInventoryChange(listener: (paths: ReadonlyArray<string> | null) => void): () => void;
  /** Hear when *path* changes, through the page's event stream; returns a disposer. A page
   *  with no stream, such as a pinned revision's, never calls back. */
  watchFile(path: string, options: MetabrowserFileWatchOptions): () => void;
  fetchKpressRender(
    ctx: MetabrowserRenderContext,
    viewId?: string,
    options?: Record<string, unknown>,
  ): Promise<KpressRenderPayload>;
  /** GET a data hook; an array value repeats its parameter, one value each. */
  fetchPluginData(
    plugin: string,
    endpoint: string,
    params: Record<string, unknown>,
    options?: { signal?: AbortSignal },
  ): Promise<MetabrowserPluginData>;
  filterControls?: MetabrowserFilterControls;
  /** How every menu closes (docs/plugins.md, "Menus"); feature-detect `menus?.dismissible`.
   *  static/filter-controls.js sets it, so a load where that script failed has none, and
   *  the shell's own callers feature-detect it too (tests/test_menu_dismissal.py). */
  menus?: MetabrowserMenus;
  filterState?: MetabrowserFilterState;
  /** A view's letter keys and badges (SDK 0.7); feature-detect `shortcuts?.attach`. */
  shortcuts?: MetabrowserPluginShortcutsApi;
  countClass(value: number): "" | "count-large";
  formatSize(value: number): string;
  formatFileCount(value: number): string;
  formatInteger(value: number): string;
  getRegisteredView(kind: string, view: string): MetabrowserViewSpec | undefined;
  icons: MetabrowserIconRegistry;
  highlightSyntax(
    source: string,
    language: string,
    options?: { signal?: AbortSignal },
  ): Promise<MetabrowserSyntaxTokenLines | null>;
  isLargeTextPreview(data: Record<string, unknown>): boolean;
  ensureAsset(name: string): Promise<void>;
  /** The namespace of an on-demand module bundle, imported once. */
  ensureModule(name: string): Promise<unknown>;
  /** The absolute URL of an on-demand module bundle, or null for a name that is not one. */
  moduleUrl(name: string): string | null;
  ensureKindAssets(kind: string): Promise<void>;
  /** Run *callback* when the page is idle, no later than *timeout* ms; returns its cancel. */
  whenIdle(callback: () => void, options?: { timeout?: number }): () => void;
  /** Wire KPress's table of contents in *container*; *config* is KPress's per-binding
   * configuration, such as the narrow toggle's `visible` policy. */
  kpressInitToc(
    container: HTMLElement,
    config?: { visible?: (context: { scrollTop(): number }) => boolean },
  ): (() => void) | null;
  langForExtension(ext: string): string;
  langForPath(pathOrName: string, ext?: string): string;
  loadKpressAssets(manifest: KpressAssetManifest): Promise<void>;
  /** The shared changed-files tree model, loaded once on demand (static/changed-files-tree.js). */
  loadChangedFilesTree(): Promise<MetabrowserChangedFilesTree>;
  /**
   * What a link in authored text opens (static/repository-links.js). Resolves to null off
   * GitHub repository pages or when the load fails or exceeds its shared deadline.
   * Later calls can use the resolver after it arrives (static/plugin-sdk-views.js).
   */
  loadRepositoryLinks(): Promise<MetabrowserRepositoryLinksRuntime | null>;
  navigation: MetabrowserNavigationApi;
  sourceKind(): "filesystem" | "git_revision";
  /**
   * The trust profile this page was served under, from the `CAPABILITIES` block the
   * server writes into `METABROWSER_SETTINGS` (capabilities.py). A pinned revision's page
   * is always inert, and a page served without the block reads as inert.
   */
  capabilities(): Readonly<{ activeContent: boolean; mutations: boolean }>;
  /**
   * The actions the page's host carries out beyond what any browser does, by name, from
   * the frozen `window.metabrowserHost` the host defines before the page's scripts run.
   * The macOS app defines one (apps/macos OpenFileRequests.swift); a browser defines
   * none, so it supports nothing. A plugin asks about an action, never about which host
   * it is in. It is a hint for what to draw: the host checks every request itself.
   */
  host: Readonly<{ actions(): string[]; supports(action: string): boolean }>;
  repository: MetabrowserRepositoryContext | null;
  perf: MetabrowserPerf;
  registerView(kind: string, view: string, spec: MetabrowserViewSpec): void;
  setViewPrintState(
    container: HTMLElement,
    state: { printable: boolean; profile?: string; runtime?: string },
  ): void;
  renderTextTruncationWarning(data: Record<string, unknown>): string;
  renderTextLoadMoreFooter(data: Record<string, unknown>): string;
  renderSourceView(
    container: HTMLElement,
    data: Record<string, unknown> & { content?: string; ext?: string },
    options?: { parts?: ReadonlyArray<Readonly<{ text: string; language: string }>> },
  ): void;
  partialNoticeHtml(
    progress: { loaded: string; total: string },
    position: "top" | "bottom",
    options?: {
      useSiteClass?: string;
      action?: string | null;
      hidden?: boolean;
      label?: string;
      showControl?: boolean;
    },
  ): string;
  sizeClass(value: number): "" | "size-large";
  sizeHtml(value: number | null | undefined, extraClass?: string): string;
  wrapWithCopy(html: string): string;
  /** ` data-mb-owner="…"`: the per-page mark the copy and Load more delegates require. */
  delegateOwnerAttribute(): string;
  /** Set that mark on a delegated control page code created; returns the element. */
  ownDelegate<T extends Element>(element: T): T;
  viewState: Readonly<{
    isActive(container: HTMLElement): boolean;
    subscribeActive(container: HTMLElement, listener: (active: boolean) => void): () => void;
  }>;
};

type StructuredPreviewGlobal = {
  calculateOptimalExpansion: StructuredExports["calculateOptimalExpansion"];
  formatValue: (...args: Array<unknown>) => unknown;
  generateStructuredPreview: (...args: Array<unknown>) => unknown;
};

type StructuredTreeGlobal = {
  expansion: StructuredExpansion;
  materializeRows: StructuredExports["materializeRows"];
  renderRowHtml: StructuredExports["renderRowHtml"];
  renderInlineTree: (
    container: HTMLElement,
    data: unknown,
    options?: Record<string, unknown>,
  ) => DisposableHandle | undefined;
};

type MetabrowserTreeExpansionNode = {
  children?: Array<MetabrowserTreeExpansionNode> | null;
  empty?: boolean;
  expanded?: boolean;
  gitignored?: boolean;
  name: string;
  path: string;
  type: string;
};

type MetabrowserTreeExpansion = {
  chooseDefaultExpandedPaths(
    nodes: Array<MetabrowserTreeExpansionNode>,
    maxVisibleRows: number,
    pageSize: number,
  ): Set<string>;
  setFolderExpanded(
    row: HTMLElement,
    children: HTMLElement,
    expanded: boolean,
    instant?: boolean,
  ): void;
  toggleFolderExpanded(row: HTMLElement, children: HTMLElement): boolean;
  visibleRowBudget(viewportHeight: number, rowHeight: number, fallbackRows: number): number;
};

type MetabrowserRecentEntry = {
  /** A Git revision's folders above the file, as a person reads them; its path is wires. */
  dir_names?: string[];
  ext?: string;
  gitignored?: boolean;
  logical_ext?: string;
  mtime?: number;
  name?: string;
  path: string;
  size?: number;
  type: "file";
};

type MetabrowserRecentFsEntry = {
  ext?: string;
  gitignored?: boolean;
  mtime_ns?: number;
  name?: string;
  path: string;
  size?: number;
  type: string;
};

type MetabrowserRecentFsChange =
  | { entry: MetabrowserRecentFsEntry; op: "upsert" }
  | { op: "remove"; path: string };

type MetabrowserRecentBatchEffect = Readonly<{
  changed: boolean;
  needsAuthoritativeRepair: boolean;
  overflowed: boolean;
  removedDescendants: number;
  retainedLowerBound: number | null;
  truncated: boolean;
}>;

type MetabrowserRecentCatalogEffect = Readonly<{
  changed: boolean;
  needsAuthoritativeRepair: boolean;
  removedEntries: number;
  retainedLowerBound: number | null;
}>;

type MetabrowserRecentRequest = {
  dirty: boolean;
  key: string;
};

type MetabrowserRecentRefetch = {
  preserveRows?: boolean;
  requestKey: string;
  windowKey: string;
};

type MetabrowserRecentFilterCursor = Readonly<{
  groupedRequestKey: string;
  recentRequestKey: string;
  source: "recent" | "tree" | "grouped";
  treeRequestKey: string;
  windowKey: string;
}>;

type MetabrowserRecentLoad = Readonly<{
  cursor: MetabrowserRecentFilterCursor;
  repair: MetabrowserRecentRefetch;
  request: MetabrowserRecentRequest;
  url: string;
}>;

type MetabrowserRecentRepairStatus = "fresh" | "retrying" | "stale";

type MetabrowserRecentInvalidationContext = {
  filterRefetchPending: boolean;
  recentActive: boolean;
  repair: MetabrowserRecentRefetch;
};

type MetabrowserRecentRepairContext = {
  current: boolean;
  fetch(windowKey: string, preserveRows: boolean): void;
  filterRefetchPending: boolean;
  recentLoaded: boolean;
  viewCommitted: boolean;
};

type MetabrowserRecentSuccessContext = {
  commit(): void;
  current: boolean;
  render(): void;
};

type MetabrowserRecentFailureContext = {
  classify(error: unknown): { retryable: boolean };
  current: boolean;
  showInitialError(): void;
};

type MetabrowserRecentContinuity = {
  abandonRequest(request?: MetabrowserRecentRequest | null): void;
  cancelRepairs(): void;
  dirtyActiveRequest(): void;
  hasActiveRequest(): boolean;
  invalidate(
    recentActive: boolean,
    filterRefetchPending: boolean,
    request: MetabrowserRecentRefetch,
  ): "ignore" | "dirty" | "covered" | "repair";
  observeSentinel(
    recentActive: boolean,
    filterRefetchPending: boolean,
    request: MetabrowserRecentRefetch,
  ): Readonly<{
    disposition: "ignore" | "dirty" | "covered" | "repair";
    phase: "baseline" | "reconnect";
  }>;
  pending(): boolean;
  repairFailed(
    request: MetabrowserRecentRefetch,
    retryable: boolean,
  ): "ignored" | "retrying" | "stale";
  repairReady(
    recentActive: boolean,
    filterRefetchPending: boolean,
  ): "ignore" | "dirty" | "covered" | "repair";
  repairSucceeded(request: MetabrowserRecentRefetch): void;
  scheduleRepair(
    request: MetabrowserRecentRefetch,
    delayMs?: number,
  ): "scheduled" | "coalesced" | "exhausted";
  startRequest(key: string): MetabrowserRecentRequest;
  status(): MetabrowserRecentRepairStatus;
  settleRequest(request: MetabrowserRecentRequest): "commit" | "refetch" | "superseded";
};

type MetabrowserGroupedLoad = {
  current(): boolean;
  first: boolean;
  key: string;
  refreshAfter(): void;
  signal: AbortSignal;
};

type MetabrowserTreeFilterModel = {
  GROUP_BY_VALUES: ReadonlyArray<string>;
  ageGroupFor(ageSeconds: number, windows: Record<string, number | null>): string;
  createGroupedLoads(deps: {
    pending(load: { first: boolean; key: string } | null): void;
    refresh(): void;
    run(load: MetabrowserGroupedLoad): Promise<boolean>;
  }): {
    cancel(): void;
    inFlight(): { first: boolean; key: string } | null;
    load(key: string, options?: { painted?: boolean; refresh?: boolean }): Promise<boolean>;
    settled(): Promise<void>;
  };
  createGroupsPrefetch(deps: {
    clearTimer(timer: unknown): void;
    dwellMs: number;
    now(): number;
    setTimer(callback: () => void, ms: number): unknown;
    start(url: string): { abort(): void; answer: Promise<unknown> };
    ttlMs: number;
  }): {
    cancelRest(): void;
    markChanged(): void;
    rest(url: string | null, stillThere?: () => boolean): void;
    resting(): boolean;
    size(): number;
    take(url: string): { abort(): void; answer: Promise<unknown>; stale: boolean } | null;
    want(url: string): void;
  };
  groupedLoadDecision(
    inFlight: { first: boolean; key: string } | null,
    asked: { first: boolean; key: string },
  ): "after" | "start";
  regroupingStatusText(by: string): string;
  groupPrefetchUrl(
    value: string,
    state: MetabrowserFilterSnapshot | null,
    sizeFloors: Record<string, number>,
  ): string | null;
  graftOpenedFolders(
    nodes: Array<Record<string, unknown>>,
    opened: Array<string>,
    cached: (path: string) => Array<Record<string, unknown>> | null | undefined,
  ): { expanded: Array<string>; fetch: Array<string>; tree: Array<Record<string, unknown>> };
  likelySectionKey(
    by: string,
    entry: { ext?: string; mtime?: number; name: string; type: string } | null,
    nowSec: number,
    windows: Record<string, number | null>,
    groupForFile: (name: string, ext: string) => string | null | undefined,
  ): string | null;
  revealSectionOrder(sectionKeys: Array<string>, likelyKey: string | null): Array<string>;
  sectionRowBudget(budget: number, sectionCount: number): number;
  groupBy(state: MetabrowserFilterSnapshot | null): string;
  groupSections(payload: unknown): Array<MetabrowserTreeSection>;
  groupTreeUrl(
    path: string,
    groupKey: string,
    state: MetabrowserFilterSnapshot | null,
    sizeFloors: Record<string, number>,
    extraParams?: Array<string>,
  ): string;
  groupedRequestKey(
    state: MetabrowserFilterSnapshot | null,
    sizeFloors: Record<string, number>,
  ): string;
  groupedRequestParams(
    state: MetabrowserFilterSnapshot | null,
    sizeFloors: Record<string, number>,
  ): Array<string>;
  groupsUrl(
    state: MetabrowserFilterSnapshot | null,
    sizeFloors: Record<string, number>,
    depth: number,
  ): string;
  beginRecentRequest(
    continuity: MetabrowserRecentContinuity,
    cursor: MetabrowserRecentFilterCursor,
    preserveRows: boolean,
  ): MetabrowserRecentLoad;
  applyRecentChangeBatch(
    entries: Map<string, MetabrowserRecentEntry>,
    operations: MetabrowserRecentFsChange[],
    options: {
      filterState: {
        rowMatches(
          row: { ext?: string; mtime?: number; path?: string; size?: number },
          state: MetabrowserFilterSnapshot,
          nowSec: number,
        ): boolean;
      };
      limit: number;
      nowSec: number;
      previousEntries: Map<string, { type?: string }>;
      state: MetabrowserFilterSnapshot;
      truncated: boolean;
    },
  ): MetabrowserRecentBatchEffect;
  applyRecentCatalogChange(
    entries: Map<string, MetabrowserRecentEntry>,
    change: MetabrowserCatalogChangePayload | null | undefined,
    options: {
      filterState: {
        rowMatches(
          row: { ext?: string; mtime?: number; path?: string; size?: number },
          state: MetabrowserFilterSnapshot,
          nowSec: number,
        ): boolean;
      };
      nowSec: number;
      state: MetabrowserFilterSnapshot;
      visibleDepth: number;
    },
  ): MetabrowserRecentCatalogEffect;
  createRecentRefetchScheduler(
    delayMs: number,
    callback: (request: MetabrowserRecentRefetch) => void,
    clock: {
      clearTimeout(handle: number): void;
      setTimeout(callback: () => void, delayMs: number): number;
    },
  ): {
    cancel(): void;
    pending(): boolean;
    schedule(request: MetabrowserRecentRefetch): void;
  };
  createRecentRecomputeScheduler(
    delayMs: number,
    callback: (request: MetabrowserRecentRefetch) => void,
    isCurrent: (request: MetabrowserRecentRefetch) => boolean,
    clock: {
      clearTimeout(handle: number): void;
      setTimeout(callback: () => void, delayMs: number): number;
    },
  ): {
    cancel(): void;
    pending(): boolean;
    schedule(request: MetabrowserRecentRefetch): "coalesced" | "scheduled";
  };
  createRecentRepairScheduler(
    delayMs: number,
    callback: (request: MetabrowserRecentRefetch) => void,
    clock: {
      clearTimeout(handle: number): void;
      setTimeout(callback: () => void, delayMs: number): number;
    },
  ): {
    cancel(): void;
    pending(): boolean;
    schedule(request: MetabrowserRecentRefetch, delayMs?: number): void;
  };
  createRecentContinuity(options: {
    clock: {
      clearTimeout(handle: number): void;
      setTimeout(callback: () => void, delayMs: number): number;
    };
    delayMs: number;
    maxRetries: number;
    maxRetryDelayMs: number;
    onRepair(request: MetabrowserRecentRefetch): void;
    onStatus?(status: MetabrowserRecentRepairStatus): void;
    retryBaseMs: number;
  }): MetabrowserRecentContinuity;
  createRecentRequest(key: string): MetabrowserRecentRequest;
  dirtyRecentRequest(request: MetabrowserRecentRequest | null): void;
  invalidateRecent(
    continuity: MetabrowserRecentContinuity,
    context: MetabrowserRecentInvalidationContext,
  ): "ignore" | "dirty" | "covered" | "repair";
  observeRecentSentinel(
    continuity: MetabrowserRecentContinuity,
    context: MetabrowserRecentInvalidationContext,
  ): Readonly<{
    disposition: "ignore" | "dirty" | "covered" | "repair";
    phase: "baseline" | "reconnect";
  }>;
  recentFilterCursor(
    state: MetabrowserFilterSnapshot | null,
    limit: number,
    sizeFloors: Record<string, number>,
  ): MetabrowserRecentFilterCursor;
  recentFilterTransition(
    previous: MetabrowserRecentFilterCursor | null,
    current: MetabrowserRecentFilterCursor,
  ): Readonly<{
    action: "apply" | "load-groups" | "load-recent" | "load-tree" | "refetch-recent";
    current: MetabrowserRecentFilterCursor;
  }>;
  /** The Files filter's remark in parts, each number apart from its words, to paint bold. */
  filteredTallyParts(
    count: number,
    recent: {
      totalMatching: number;
      totalMatchingExact: boolean;
      truncated: boolean;
    } | null,
  ): MetabrowserCountParts;
  recentRequestDisposition(
    active: MetabrowserRecentRequest | null,
    request: MetabrowserRecentRequest,
  ): "commit" | "refetch" | "superseded";
  recentRepairDisposition(
    recentActive: boolean,
    requestInFlight: boolean,
    filterRefetchPending: boolean,
  ): "ignore" | "dirty" | "covered" | "repair";
  recentRequestKey(
    windowKey: string,
    limit: number,
    state: MetabrowserFilterSnapshot | null,
    sizeFloors: Record<string, number>,
  ): string;
  recentViewOwnsCursor(
    committed: MetabrowserRecentRefetch | null,
    cursor: MetabrowserRecentFilterCursor,
  ): boolean;
  recentEntryMatches(
    entry: MetabrowserRecentEntry | null | undefined,
    options: {
      filterState: {
        rowMatches(
          row: { ext?: string; mtime?: number; path?: string; size?: number },
          state: MetabrowserFilterSnapshot,
          nowSec: number,
        ): boolean;
      };
      nowSec: number;
      state: MetabrowserFilterSnapshot;
    },
  ): boolean;
  recentUrl(
    windowKey: string,
    limit: number,
    state: MetabrowserFilterSnapshot | null,
    sizeFloors: Record<string, number>,
  ): string;
  recentView(
    entries: MetabrowserRecentEntry[],
    options: {
      clusterPct: number;
      filterState: {
        rowMatches(
          row: { ext?: string; mtime?: number; path?: string; size?: number },
          state: MetabrowserFilterSnapshot,
          nowSec: number,
        ): boolean;
      };
      ignoredDirectoryPaths: Set<string>;
      limit: number;
      nowSec: number;
      state: MetabrowserFilterSnapshot;
    },
  ): { entries: MetabrowserRecentEntry[]; matchingCount: number; tree: TreeNode[] };
  renderRecentView(
    entries: MetabrowserRecentEntry[],
    options: {
      clusterPct: number;
      filterState: {
        rowMatches(
          row: { ext?: string; mtime?: number; path?: string; size?: number },
          state: MetabrowserFilterSnapshot,
          nowSec: number,
        ): boolean;
      };
      ignoredDirectoryPaths: Set<string>;
      limit: number;
      nowSec: number;
      state: MetabrowserFilterSnapshot;
    },
    render: (view: {
      entries: MetabrowserRecentEntry[];
      matchingCount: number;
      tree: TreeNode[];
    }) => void,
  ): { entries: MetabrowserRecentEntry[]; matchingCount: number; tree: TreeNode[] };
  requestKey(state: MetabrowserFilterSnapshot | null, sizeFloors: Record<string, number>): string;
  requestParams(
    state: MetabrowserFilterSnapshot | null,
    sizeFloors: Record<string, number>,
  ): string[];
  runRecentRepair(
    continuity: MetabrowserRecentContinuity,
    request: MetabrowserRecentRefetch,
    context: MetabrowserRecentRepairContext,
  ): "cancelled" | "ignore" | "dirty" | "covered" | "repair";
  settleRecentFailure(
    continuity: MetabrowserRecentContinuity,
    request: MetabrowserRecentRequest,
    repair: MetabrowserRecentRefetch,
    error: unknown,
    context: MetabrowserRecentFailureContext,
  ): "ignored" | "repair-failed" | "repair-scheduled" | "initial-failed";
  settleRecentSuccess(
    continuity: MetabrowserRecentContinuity,
    request: MetabrowserRecentRequest,
    repair: MetabrowserRecentRefetch,
    context: MetabrowserRecentSuccessContext,
  ): "ignored" | "repair-scheduled" | "committed";
  treeUrl(
    path: string,
    state: MetabrowserFilterSnapshot | null,
    sizeFloors: Record<string, number>,
    extraParams?: string[],
  ): string;
  trimRecentEntriesToLimit(entries: Map<string, MetabrowserRecentEntry>, limit: number): boolean;
};

type MetabrowserPendingTallyWatchdog = Readonly<{
  dispose(): void;
  reconcile(): void;
}>;

type MetabrowserPendingTallyDiagnosticsRuntime = Readonly<{
  create(options: {
    cancel?: (handle: number) => void;
    collect(context: { elapsedMs: number; episode: number }): unknown;
    delayMs: number;
    hasPending(): boolean;
    now?: () => number;
    onError?: (error: unknown) => void;
    report(payload: unknown): unknown | Promise<unknown>;
    schedule?: (callback: () => void, delayMs: number) => number;
  }): MetabrowserPendingTallyWatchdog;
}>;

type MetabrowserKnownFileCatalogWireEntry = {
  children?: Array<MetabrowserKnownFileCatalogWireEntry> | null;
  gitignored?: boolean;
  logical_ext?: string;
  name?: string;
  path: string;
  type: string;
};

type MetabrowserKnownFile = Readonly<{
  basename: string;
  logicalExtension: string | null;
  path: string;
  source: string;
}>;

/**
 * Root coverage of the known-file catalog. `complete` is a finished walk that
 * did not hit the inventory file cap; `truncated` is a finished walk that did,
 * so membership is final for the index but does not cover the root.
 */
type MetabrowserKnownFileCatalogCoverage = "partial" | "truncated" | "complete";

type MetabrowserKnownFileCatalogSnapshot = Readonly<{
  /** The catalog covers every file under the root. */
  complete: boolean;
  /**
   * Safe canonical POSIX-relative file paths in ascending UTF-16 code-unit
   * order. The catalog rejects absolute, empty-segment, dot-segment,
   * backslash, NUL, trailing-slash, and unpaired-surrogate spellings. It does
   * not impose a length ceiling; consumers bound only paths they operate on.
   */
  files: ReadonlyArray<MetabrowserKnownFile>;
  observedCount: number;
  revision: number;
  sourceSummary: Readonly<Record<string, number>>;
  /**
   * The walk reached its terminal state at the inventory file cap. The walk adds
   * no more files for this index, but files past the cap were never indexed, so
   * a lookup miss is not proof of absence. Never true together with `complete`.
   */
  truncated: boolean;
}>;

type MetabrowserCatalogChangePayload = {
  non_file_paths?: string[];
  remove_files?: string[];
  upserts?: Array<{ p: string; e: string }>;
  removes?: string[];
};

type MetabrowserBulkSnapshotStep = Readonly<{
  candidateVisits: number;
  cancelled: boolean;
  done: boolean;
  workItems: number;
}>;

type MetabrowserBulkSnapshotApplication = Readonly<{
  cancel(): void;
  enqueueCatalogChange(payload: MetabrowserCatalogChangePayload): void;
  enqueueEventChange(ops: MetabrowserEventChangeOperation[]): void;
  step(maxWorkItems: number): MetabrowserBulkSnapshotStep;
}>;

type MetabrowserEventChangeOperation = {
  entry?: MetabrowserKnownFileCatalogWireEntry;
  op: string;
  path?: string;
};

type MetabrowserCatalogMutationResult = Readonly<{
  candidateVisits: number;
  changed: boolean;
  workItems: number;
}>;

type MetabrowserKnownFileCatalogApi = Readonly<{
  /**
   * @param bulkCoverage the root coverage the payload establishes: `complete`
   *   for a finished walk that did not hit the max-files cap, `truncated` for
   *   one that did, `partial` otherwise. It never lowers current coverage.
   * @param authoritative the payload lists every file the index holds, so
   *   feed-sourced paths it omits are stale and get retired. False for a
   *   payload built mid-walk, which is only a prefix.
   */
  beginBulkSnapshot(
    files: Array<{ p: string; e: string }>,
    bulkCoverage: MetabrowserKnownFileCatalogCoverage,
    authoritative?: boolean,
  ): MetabrowserBulkSnapshotApplication;
  beginCatalogChange(
    payload: MetabrowserCatalogChangePayload,
    maxWorkItems: number,
  ): MetabrowserBulkSnapshotApplication | null;
  beginEventChange(
    ops: MetabrowserEventChangeOperation[],
    maxWorkItems: number,
  ): MetabrowserBulkSnapshotApplication | null;
  applyCatalogChange(payload: MetabrowserCatalogChangePayload): MetabrowserCatalogMutationResult;
  applyEventChange(ops: MetabrowserEventChangeOperation[]): MetabrowserCatalogMutationResult;
  clear(): void;
  markComplete(): void;
  markIncomplete(): void;
  /** Record a terminal walk that stopped at the file cap; never lowers complete. */
  markTruncated(): void;
  observeEventSnapshot(entries: Array<MetabrowserKnownFileCatalogWireEntry>): void;
  observeInitialTree(entries: Array<MetabrowserKnownFileCatalogWireEntry>): void;
  observeLazyTree(entries: Array<MetabrowserKnownFileCatalogWireEntry>): void;
  observeNavigation(path: string, logicalExtension: string | null): void;
  observeRecent(entries: Array<MetabrowserKnownFileCatalogWireEntry>): void;
  observeTree(entries: Array<MetabrowserKnownFileCatalogWireEntry>, source: string): void;
  removePath(path: string): void;
  snapshot(): MetabrowserKnownFileCatalogSnapshot;
  /**
   * Observe every catalog mutation. Returns an unsubscribe function.
   *
   * Invalidation only: the listener is told the catalog moved, not what it
   * moved to. Call `snapshot()` when the state is needed; its maintained
   * immutable projection contains only safe canonical logical-file paths and
   * is already in code-unit order. A listener that writes back does not
   * re-enter.
   */
  subscribe(listener: () => void): () => void;
}>;

type MetabrowserKnownFileCatalogRuntime = Readonly<{
  create(): MetabrowserKnownFileCatalogApi;
}>;

type MetabrowserPublicFileCatalogApi = Readonly<{
  snapshot(): MetabrowserKnownFileCatalogSnapshot;
  subscribe(listener: () => void): () => void;
}>;

type MetabrowserPluginHostRuntime = Readonly<{
  attachFileCatalog(catalog: MetabrowserKnownFileCatalogApi): () => void;
  /** The shell names a partial-content notice's Load more action; see plugin-sdk.js. */
  registerLoadMoreAction(name: string, action: () => unknown): void;
  /** Whether page code marked this element as a delegated control; see plugin-sdk.js. */
  isOwnedDelegate(element: Element | null | undefined): boolean;
  /** Whether `ownDelegate` marked this very element, not a copy of its mark. */
  ownsElement(element: Element | null | undefined): boolean;
  /** Keys still held from before static/plugin-shortcuts.js loaded; it empties this. */
  shortcutQueue: Set<MetabrowserQueuedShortcut>;
  /** Each plugin's assets by name, and the plugins each kind's views come from. */
  configureAssets(config: {
    plugins: Record<string, PluginAssets>;
    kinds: Record<string, string[]>;
  }): void;
  loadPluginsForKind(kind: string): Promise<void>;
}>;

type MetabrowserCatalogFeedApi = Readonly<{
  dispose(): void;
  onCatalogChange(payload: MetabrowserCatalogChangePayload): void;
  onEventChange(ops: MetabrowserEventChangeOperation[]): void;
  onIndexComplete(truncated?: boolean): void;
  onResync(): void;
  onSentinelSnapshot(): void;
  start(): void;
  /** Keep the bulk fetch from starting until `release`. */
  hold(): void;
  release(): void;
}>;

type MetabrowserCatalogFeedRuntime = Readonly<{
  BULK_APPLY_SLICE_ITEMS: number;
  create(options: {
    catalog: Pick<
      MetabrowserKnownFileCatalogApi,
      | "applyCatalogChange"
      | "applyEventChange"
      | "beginBulkSnapshot"
      | "beginCatalogChange"
      | "beginEventChange"
      | "markComplete"
      | "markIncomplete"
    >;
    endpoint?: string;
    fetchImpl?: typeof fetch;
    scheduleRetry?: (callback: () => void, delayMs: number) => number;
    cancelRetry?: (handle: number) => void;
    yieldControl?: () => Promise<void>;
  }): MetabrowserCatalogFeedApi;
}>;

type MetabrowserFuzzyRank = Readonly<{
  matchClass: number;
  boundaryHits: number;
  contiguousChars: number;
  runCount: number;
  gapChars: number;
  startOffset: number;
  candidateLength: number;
  directoryDepth: number;
  normalizedPath: string;
  originalPath: string;
}>;

type MetabrowserFuzzyMatch = Readonly<{
  matchRanges: ReadonlyArray<Readonly<{ start: number; end: number }>>;
  path: string;
  rank: MetabrowserFuzzyRank;
}>;

type MetabrowserFileFuzzyMatchRuntime = Readonly<{
  compareMatches(left: MetabrowserFuzzyMatch, right: MetabrowserFuzzyMatch): number;
  matchPath(query: string, path: string): MetabrowserFuzzyMatch | null;
  rankPaths(query: string, paths: string[], limit?: number): ReadonlyArray<MetabrowserFuzzyMatch>;
}>;

type MetabrowserSearchRequest = Readonly<{
  match: "fuzzy";
  query: string;
  target: "all" | "file";
}>;

type MetabrowserSearchFileResult = Readonly<{
  description: string;
  id: string;
  kind: "file";
  label: string;
  logicalExtension?: string | null;
  matchRanges: ReadonlyArray<Readonly<{ start: number; end: number }>>;
  path: string;
  providerId: string;
  rank?: MetabrowserFuzzyRank;
  score: number;
}>;

type MetabrowserSearchPullState = "open" | "draft" | "closed" | "merged";

type MetabrowserSearchPullResult = Readonly<{
  id: string;
  kind: "pull";
  label: string;
  matchRanges: ReadonlyArray<Readonly<{ start: number; end: number }>>;
  number: number;
  providerId: string;
  score: number;
  state: MetabrowserSearchPullState;
}>;

type MetabrowserSearchResult = MetabrowserSearchFileResult | MetabrowserSearchPullResult;

type MetabrowserSearchBatch = Readonly<{
  candidateCount?: number;
  complete: boolean;
  providerId: string;
  results: ReadonlyArray<MetabrowserSearchResult>;
  revision?: number;
  statusMessage?: string;
  truncated: boolean;
}>;

type MetabrowserSearchContext = Readonly<{
  requestId: number;
  publishBatch?(batch: MetabrowserSearchBatch): void;
}>;

type MetabrowserSearchProvider = Readonly<{
  activation?: "fallback" | "immediate";
  id: string;
  priority?: number;
  search(
    request: MetabrowserSearchRequest,
    context: MetabrowserSearchContext,
    signal: AbortSignal,
  ): MetabrowserSearchBatch | Promise<MetabrowserSearchBatch>;
  supports?(request: MetabrowserSearchRequest): boolean;
}>;

type MetabrowserSearchState = Readonly<{
  batches: ReadonlyArray<
    Readonly<{
      candidateCount?: number;
      complete: boolean;
      providerId: string;
      resultCount: number;
      revision?: number;
      statusMessage?: string;
      truncated: boolean;
    }>
  >;
  complete: boolean;
  errors: ReadonlyArray<string>;
  phase: "idle" | "searching" | "complete";
  request: MetabrowserSearchRequest | null;
  requestId: number;
  results: ReadonlyArray<MetabrowserSearchResult>;
  statusMessage: string;
  truncated: boolean;
}>;

type MetabrowserSearchController = Readonly<{
  cancel(): void;
  dispose(): void;
  registerProvider(provider: MetabrowserSearchProvider): () => void;
  search(
    request: MetabrowserSearchRequest,
    options?: { includeFallback?: boolean },
  ): Promise<MetabrowserSearchState | null>;
  state(): MetabrowserSearchState;
  subscribe(listener: (state: MetabrowserSearchState) => void): () => void;
}>;

type MetabrowserSearchRuntime = Readonly<{
  /** Rows pull requests have after the files' cap. */
  PULL_RESULT_LIMIT: number;
  createController(options?: { maxResults?: number }): MetabrowserSearchController;
  createLocalFileProvider(options: {
    catalog: MetabrowserKnownFileCatalogApi;
    chunkSize?: number;
    matcher: MetabrowserFileFuzzyMatchRuntime;
    maxResults?: number;
    syncThreshold?: number;
    yieldControl?: (signal: AbortSignal) => Promise<void>;
  }): MetabrowserSearchProvider;
  createPullProvider(options?: {
    fetch?: typeof fetch;
    maxResults?: number;
  }): MetabrowserSearchProvider;
  isExplicitPullQuery(query: string): boolean;
}>;

/** A failed open always says why, so the palette never has to classify it again. */
type MetabrowserOpenFileOutcome = Readonly<
  | {
      focusTarget?: HTMLElement | null;
      message?: string;
      status: "opened" | "not-found" | "cancelled";
    }
  | {
      focusTarget?: HTMLElement | null;
      message: string;
      status: "error" | "unreachable";
    }
>;

type MetabrowserSearchPaletteApi = Readonly<{
  close(): void;
  dispose(): void;
  element: HTMLElement;
  isOpen(): boolean;
  open(trigger?: HTMLElement | null): void;
  /** The server answers again: retire a status that says it is unreachable. */
  reconnected(): void;
}>;

type MetabrowserSearchPaletteRuntime = Readonly<{
  create(options: {
    controller: MetabrowserSearchController;
    /** Describe an open that threw, distinguishing an unreachable server. */
    describeOpenFailure(
      error: unknown,
    ): Readonly<{ message: string; status: "error" | "unreachable" }>;
    document?: Document;
    getCatalogSnapshot(): { complete: boolean; observedCount: number; truncated: boolean };
    getFileIcon?(path: string): { cls?: string; svg?: string };
    maxRows?: number;
    onNotFound?(path: string): void | Promise<void>;
    onOpen?(): void;
    openFile(path: string): MetabrowserOpenFileOutcome | Promise<MetabrowserOpenFileOutcome>;
    openPull?(number: number): MetabrowserOpenFileOutcome | Promise<MetabrowserOpenFileOutcome>;
    overlay: MetabrowserOverlayRuntime;
    resolveFocusFallback?(previous: HTMLElement | null): HTMLElement | null;
    shortcuts: MetabrowserShortcutRegistry;
    /**
     * Observe catalog growth so an open search converges instead of keeping
     * the coverage it had when the query ran. Returns an unsubscribe function.
     */
    subscribeCatalog?(listener: () => void): () => void;
  }): MetabrowserSearchPaletteApi;
}>;

/**
 * One key, or Control with a letter of `CONTROL_CHORD_KEYS` (`control: true`), registered
 * only where `controlReachesPage()`: a binding states no other modifier policy, and Shift
 * never changes a key.
 */
type MetabrowserShortcutBinding = Readonly<{
  control?: true;
  key: string;
}>;

/** A key the formatter names: its ARIA token, spoken name, and keycap label. */
type MetabrowserKeyDefinition = Readonly<{ aria: string; spoken: string; visible: string }>;

/**
 * A registry publication. A batch that changed more than one thing publishes one
 * `batch` event naming each kind it contained.
 */
type MetabrowserShortcutEvent = Readonly<{
  commandId?: string;
  kind: string;
  kinds?: ReadonlyArray<string>;
  scope?: string;
}>;

type MetabrowserBindingPresentation = Readonly<{
  ariaKeyshortcuts: string;
  preferred?: MetabrowserBindingPresentation;
  /** The keycaps are a run's two ends, the situational numbers 1 to 9, not alternatives. */
  range?: boolean;
  spoken: string;
  /** One keycap label per alternative: a single key, or a Control chord such as `⌃N`. */
  visible: ReadonlyArray<string>;
}>;

type MetabrowserShortcutControlBinding = Readonly<{
  connect(element: HTMLElement): () => void;
}>;

type MetabrowserShortcutCommand = Readonly<{
  allowInEditable?: boolean;
  available?(context: Record<string, unknown>): boolean;
  bindings: ReadonlyArray<MetabrowserShortcutBinding>;
  control?: MetabrowserShortcutControlBinding;
  copy: Readonly<{ action: string; description: string; hint: string }>;
  group: string;
  handler(context: Record<string, unknown>): boolean;
  id: string;
  order: number;
  repeat?: boolean;
  scope: string;
  surfaces: Readonly<Record<string, "active" | "always">>;
  /** Live only while one of its attached targets is live; see `attachTarget`. */
  targeted?: boolean;
  /** Its bindings are positional numbers no control owns, presented as one run. */
  situational?: boolean;
}>;

/** Where a badge sits: inside its target, or past its inline end in a badge anchor. */
type MetabrowserBadgePlacement = "beside" | "inline-end";

/** What `attachTarget` returns: move the target after a rebuild, or let it go. */
type MetabrowserShortcutTarget = Readonly<{
  detach(): void;
  retarget(element: HTMLElement): void;
}>;

type MetabrowserShortcutPresentation = Readonly<{
  bindings: MetabrowserBindingPresentation;
  control?: MetabrowserShortcutControlBinding;
  copy: Readonly<{ action: string; description: string; hint: string }>;
  commandIds: ReadonlyArray<string>;
  group: string;
  id: string;
  scope: string;
  surfaces: Readonly<Record<string, "active" | "always">>;
}>;

type MetabrowserShortcutGroupPresentation = Readonly<{
  commands: ReadonlyArray<MetabrowserShortcutPresentation>;
  context: string;
  id: string;
  label: string;
}>;

type MetabrowserShortcutRegistry = Readonly<{
  activateScope(scope: string, options?: { exclusive?: boolean }): () => void;
  appendBinding(container: HTMLElement, presentation: MetabrowserBindingPresentation): void;
  /** Render one key, a binding key or a standalone name such as `Shift`, as one keycap. */
  appendKey(container: HTMLElement, key: string): HTMLElement;
  /**
   * Record an element a command acts on: its `aria-keyshortcuts`, liveness, and badge. A
   * lower `rank` goes first among live targets, ahead of document order.
   */
  attachTarget(
    commandId: string,
    element: HTMLElement,
    options?: { placement?: MetabrowserBadgePlacement; rank?: number },
  ): MetabrowserShortcutTarget;
  /**
   * Number a situational control: its number is its place, 1 to 9, among the live
   * numbered controls in reading order, so it has no fixed key of its own.
   */
  attachNumbered(
    element: HTMLElement,
    options: { activate(): unknown; placement?: MetabrowserBadgePlacement },
  ): MetabrowserShortcutTarget;
  /** Run `work` and publish what it changed once, when the outermost batch ends. */
  batch<T>(work: () => T): T;
  /** Whether a Control chord reaches the page, on macOS and iOS; only there is one bound. */
  controlReachesPage(): boolean;
  dispose(): void;
  describeBindings(
    bindings: ReadonlyArray<MetabrowserShortcutBinding>,
  ): MetabrowserBindingPresentation;
  describeKey(key: string): MetabrowserKeyDefinition;
  /** Whether a live command in an active layer above `scope` is bound to `key` alone. */
  heldAbove(scope: string, key: string): boolean;
  invoke(commandId: string, context?: Record<string, unknown>): boolean;
  /** Whether a command would run now: active scope, `available()`, and a live target. */
  isLive(commandId: string): boolean;
  isRevealed(): boolean;
  /** Whether an element can take a key now: connected, enabled, not inert, and visible. */
  isTargetLive(element: HTMLElement): boolean;
  /** The element a command would act on now, its first live target by rank and order. */
  liveTarget(commandId: string): HTMLElement | null;
  /** The controls the numbers reach now, in order: the first is 1, and there are at most 9. */
  liveNumbers(): ReadonlyArray<HTMLElement>;
  /** Hear each key after dispatch as `(event, handled)`, and each `keyup` as unhandled. */
  observeKeys(observer: (event: KeyboardEvent, handled: boolean) => void): () => void;
  present(commandId: string): MetabrowserShortcutPresentation | null;
  /** Read target liveness again and move the badges while revealed; publishes `dispatch`. */
  refreshBadges(): void;
  register(command: MetabrowserShortcutCommand): () => void;
  /** Show or hide every badge, for the key reveal; publishes `reveal`. */
  setRevealed(revealed: boolean): void;
  snapshot(
    surface: string,
    options?: { includeInactive?: boolean; live?: boolean },
  ): ReadonlyArray<MetabrowserShortcutGroupPresentation>;
  subscribe(listener: (event: MetabrowserShortcutEvent) => void): () => void;
}>;

type MetabrowserKeyboardShortcutsRuntime = Readonly<{
  /** The letters a binding may hold with Control (`control: true`). */
  CONTROL_CHORD_KEYS: ReadonlyArray<string>;
  GROUP_DEFINITIONS: Readonly<
    Record<string, Readonly<{ context: string; label: string; order: number }>>
  >;
  KEY_DEFINITIONS: Readonly<
    Record<string, Readonly<{ aria: string; spoken: string; visible: string }>>
  >;
  /** How many situational controls the numbers reach: 1 to 9, and no more. */
  NUMBERED_LIMIT: number;
  appendBinding(
    document: Document,
    container: HTMLElement,
    presentation: MetabrowserBindingPresentation,
  ): void;
  appendKey(document: Document, container: HTMLElement, key: string): HTMLElement;
  bindingSignature(binding: MetabrowserShortcutBinding): string;
  /** Whether a Control chord reaches the page, on macOS and iOS; only there is one bound. */
  controlReachesPage(): boolean;
  create(options?: { document?: Document }): MetabrowserShortcutRegistry;
  describeBindings(
    bindings: ReadonlyArray<MetabrowserShortcutBinding>,
  ): MetabrowserBindingPresentation;
  describeKey(key: string): MetabrowserKeyDefinition;
  /** `physical` matches a digit binding by its digit-row key, the dispatcher's second pass. */
  eventMatchesBinding(
    event: KeyboardEvent,
    binding: MetabrowserShortcutBinding,
    options?: { physical?: boolean },
  ): boolean;
  isEditableTarget(target: EventTarget | null): boolean;
  normalizeBinding(binding: MetabrowserShortcutBinding): MetabrowserShortcutBinding;
  validateCommand(command: MetabrowserShortcutCommand): boolean;
}>;

type MetabrowserModalController = Readonly<{
  body: HTMLElement;
  close(options?: { restoreFocus?: boolean }): void;
  closeButton: HTMLButtonElement;
  control: MetabrowserShortcutControlBinding;
  dialog: HTMLElement;
  dispose(): void;
  element: HTMLElement;
  footer: HTMLElement;
  isOpen(): boolean;
  open(trigger?: HTMLElement | null): void;
  title: HTMLElement;
}>;

type MetabrowserOverlayRuntime = Readonly<{
  captureBackgroundState(
    document: Document,
    portal: HTMLElement,
  ): Array<{ element: HTMLElement; inert: boolean }>;
  createDialogShell(options: {
    className?: string;
    document: Document;
    title: string;
  }): Omit<MetabrowserModalController, "close" | "control" | "dispose" | "isOpen" | "open">;
  createModal(options: {
    className?: string;
    closeCommandId: string;
    document?: Document;
    initialFocus?: HTMLElement | (() => HTMLElement | null);
    onClose?(): void;
    onOpen?(): void;
    resolveFocusFallback?(previous: HTMLElement | null): HTMLElement | null;
    scope: string;
    shortcuts: MetabrowserShortcutRegistry;
    title: string;
  }): MetabrowserModalController;
  focusableElements(root: HTMLElement): Array<HTMLElement>;
  restoreBackgroundState(records: ReadonlyArray<{ element: HTMLElement; inert: boolean }>): void;
}>;

/** static/key-reveal.js: the Shift key reveal's state machine. */
type MetabrowserKeyRevealApi = Readonly<{
  dispose(): void;
  snapshot(): Readonly<{ armed: boolean; state: "armed" | "idle" | "revealed" }>;
}>;

type MetabrowserKeyRevealRuntime = Readonly<{
  REVEAL_HOLD_MS: number;
  REVEAL_POINTER_SLOP_PX: number;
  createKeyReveal(options: {
    shortcuts: MetabrowserShortcutRegistry;
    document?: Document;
    window?: Window;
    root?: HTMLElement;
    schedule?: (callback: () => void, delayMs: number) => unknown;
    cancel?: (handle: unknown) => void;
    visibility?: () => DocumentVisibilityState;
    holdMs?: number;
    slopPx?: number;
  }): MetabrowserKeyRevealApi;
}>;

/**
 * What app.js lends static/shell-keymap.js: the paths that activate the shell's controls,
 * each the one its control's click runs, and which only app.js can reach. The keymap
 * finds the main pane and the filter bar by their ids, and asks the selector's module for
 * its mounted selector.
 */
type MetabrowserShellKeymapShell = Readonly<{
  /** Home: the served folder's home view, as the folder's name's click goes there. */
  goHome(): void;
  openFolder(dir: string): void;
  /** Hide or show the navigation pane, as its chevron's click does. */
  toggleNav(): void;
  /** The chevron that hides and shows the navigation pane, the key's target. */
  navToggle(): HTMLElement | null;
  selectPreviewTab(bar: HTMLElement, tabId: string): boolean;
  /** Open or close a filter dropdown, `types` or `recency`, as its trigger's click does. */
  toggleFilterMenu(key: string, open: boolean): void;
}>;

type MetabrowserShellKeymapApi = Readonly<{
  /** Follow the bar the main pane commits, and its header, in one publication. */
  commitViewTabs(nextBar: HTMLElement | null): void;
  /** The view tab bar the main pane has committed, never one still staged. */
  committedBar(): HTMLElement | null;
  dispose(): void;
  syncFilters(): void;
  syncHeader(): void;
  /** Follow what the main pane installed: its view tab letters and its header. */
  syncPane(): void;
  syncSource(): void;
  syncViewTabs(bar: HTMLElement | null): void;
}>;

type MetabrowserShellKeymapRuntime = Readonly<{
  createShellKeymap(options: {
    shortcuts: MetabrowserShortcutRegistry;
    shell: MetabrowserShellKeymapShell;
  }): MetabrowserShellKeymapApi;
}>;

/**
 * What a plugin passes `metabrowser.shortcuts.attach()`; see docs/plugins.md. A letter
 * key names a known meaning; a situational control asks for `numbered: true` instead and
 * takes its number from its place on screen, with no letter, group, order, or copy.
 */
type MetabrowserPluginShortcutSpec = Readonly<
  {
    /** Dotted, such as `diff.layout`; one id is one command, whatever it is attached to. */
    id: string;
    /** The control's own activation path, never a synthesized click. */
    activate(): unknown;
    /** Aborting it detaches the key. */
    signal?: AbortSignal;
  } & (
    | {
        /** One ASCII letter, case ignored. */
        key: string;
        group: "controls" | "view-tabs";
        order: number;
        copy: Readonly<{ action: string; description: string; hint: string }>;
        numbered?: undefined;
      }
    | { numbered: true }
  )
>;

/** What `metabrowser.shortcuts.attach()` returns: move the key's target, or let it go. */
type MetabrowserPluginShortcutHandle = Readonly<{
  detach(): void;
  retarget(element: HTMLElement): void;
}>;

/** `window.metabrowser.shortcuts`: a plugin view's letter keys and their badges. */
type MetabrowserPluginShortcutsApi = Readonly<{
  attach(
    element: HTMLElement,
    spec: MetabrowserPluginShortcutSpec,
  ): MetabrowserPluginShortcutHandle;
}>;

/** One attachment plugin-sdk.js holds until static/plugin-shortcuts.js loads and takes it. */
type MetabrowserQueuedShortcut = {
  element: unknown;
  options: unknown;
  /** The facade's handle, once the facade took the attachment. */
  handle?: MetabrowserPluginShortcutHandle;
};

/** static/plugin-shortcuts.js: the plugin shortcut facade. */
type MetabrowserPluginShortcutsRuntime = Readonly<{
  attachShortcut(element: unknown, options: unknown): MetabrowserPluginShortcutHandle;
  /** Bind every attachment, now and later, to a registry; returns the detach. */
  attachShortcutRegistry(registry: MetabrowserShortcutRegistry): () => void;
  /** Detach every attachment whose element is inside `container`: view disposal's net. */
  releaseWithin(container: Node): void;
}>;

type MetabrowserKeyboardHelpApi = Readonly<{
  close(): void;
  dispose(): void;
  open(trigger?: HTMLElement | null): void;
}>;

type MetabrowserKeyboardHelpRuntime = Readonly<{
  create(options: {
    document?: Document;
    hintHost: HTMLElement;
    overlay: MetabrowserOverlayRuntime;
    resolveFocusFallback?(previous: HTMLElement | null): HTMLElement | null;
    shortcuts: MetabrowserShortcutRegistry;
  }): MetabrowserKeyboardHelpApi;
  reconcileHintStrip(
    host: HTMLElement,
    snapshot: ReadonlyArray<MetabrowserShortcutGroupPresentation>,
    invoke: (commandId: string, context: Record<string, unknown>) => boolean,
    append?: (container: HTMLElement, presentation: MetabrowserBindingPresentation) => void,
    options?: {
      actions?: boolean;
      bindings?: "all" | "preferred";
      lead?: HTMLElement;
      limit?: number;
    },
  ): void;
  renderHelpGroups(
    body: HTMLElement,
    snapshot: ReadonlyArray<MetabrowserShortcutGroupPresentation>,
    append?: (container: HTMLElement, presentation: MetabrowserBindingPresentation) => void,
  ): void;
  stripItemsThatFit(widths: ReadonlyArray<number>, available: number, gap: number): number;
}>;

type MetabrowserTreeMutationSnapshot = Readonly<{
  anchor: string | null;
  hadFocus: boolean;
  parent: string | null;
  siblings: Array<string>;
}>;

type MetabrowserTreeKeyboardApi = Readonly<{
  dispose(): void;
  /** Focus the roving anchor row, or the first visible row; false when there is none. */
  focusCurrent(): boolean;
  focusedRow(): HTMLElement | null;
  prepareForMutation(): MetabrowserTreeMutationSnapshot;
  setAnchor(row: HTMLElement, focus?: boolean): HTMLElement | null;
  setSelectedPath(path: string | null | undefined): void;
  synchronize(snapshot?: MetabrowserTreeMutationSnapshot | null): Array<HTMLElement>;
  visibleRows(): Array<HTMLElement>;
  walking(path: string): Promise<void> | null;
}>;

/** A held arrow key's walk through a tree: see tree-keyboard-navigation.js#createWalk. */
type MetabrowserTreeWalk = Readonly<{
  end(): void;
  step(path: string | null, repeat: boolean): void;
  walking(path: string): Promise<void> | null;
}>;

type MetabrowserTreeKeyboardRuntime = Readonly<{
  WALK_SETTLE_MS: number;
  create(options: {
    activate(
      row: HTMLElement,
    ): HTMLElement | null | undefined | Promise<HTMLElement | null | undefined>;
    container: HTMLElement;
    document?: Document;
    navigate(row: HTMLElement): void;
    setFolderExpanded(row: HTMLElement, expanded: boolean): void | Promise<void>;
    shortcuts: MetabrowserShortcutRegistry;
  }): MetabrowserTreeKeyboardApi;
  createWalk(): MetabrowserTreeWalk;
  firstChildRow(row: HTMLElement): HTMLElement | null;
  parentRow(row: HTMLElement): HTMLElement | null;
  readVisibleRows(container: HTMLElement): Array<HTMLElement>;
  rowIdentity(row: HTMLElement): string;
}>;

declare global {
  /** An age's freshness tier, as a treemap's fill reads it. */
  type MetabrowserAgeBucket = "sec" | "min" | "hr" | "day" | "wk" | "old";
  /** How an age is told: `now`, epoch seconds, is the time it is told as of, by default the
   *  clock's. */
  type MetabrowserAgeOptions = { style?: "compact" | "relative"; now?: number };
  /** How an age is drawn: `className` is the call site's own class, which places it and sets
   *  nothing of its ink; `tip` is its `data-tip-text`, the exact time. */
  type MetabrowserAgeLabelOptions = MetabrowserAgeOptions & { className?: string; tip?: string };
  /** Why a menu closed: a press outside it, focus or the window leaving it, Escape, or another menu opening. */
  type MetabrowserMenuClose = "outside" | "away" | "escape" | "other";
  /** One menu, as `metabrowser.menus.dismissible` closes it (docs/design-system.md, "Every Menu Closes Alike"). */
  type MetabrowserDismissibleMenu = {
    /** The menu's surface class beside `.menu`, which tests/test_menu_dismissal.py reads. */
    name: string;
    /** The button that opens it, or a function that finds it: inside the menu, and where Escape gives focus back. */
    trigger: HTMLElement | null | (() => HTMLElement | null);
    /** Whether a node is the menu's own, beyond its trigger: its panel, and anything it places. */
    inside(node: Node): boolean;
    isOpen(): boolean;
    /** Close it, as its own code does; the helper moves focus only for Escape. */
    close(how: MetabrowserMenuClose): void;
  };
  type MetabrowserDismissibleHandle = {
    /** Call each time the menu opens: it closes any other menu, whichever handle holds it,
     * so one menu has one handle, and starts listening. */
    opened(): void;
    /** Call when the menu's own code closes it, so the listeners go at once. */
    closed(): void;
    /** Stop for good, when the menu goes. */
    dispose(): void;
  };
  /** How every menu closes (static/menus.js). The SDK's `menus` is in the startup scripts and
   * forwards to it, asking for the shell's tools when a menu opens before they arrive. */
  type MetabrowserMenus = {
    dismissible(menu: MetabrowserDismissibleMenu): MetabrowserDismissibleHandle;
  };

  /** A watched file's new generation (`file.changed`); null when nothing readable is there. */
  type MetabrowserFileChange = { path: string; generation: string | null };
  /** Where a file watch stands: waiting for a connection (or for a hidden page to be shown,
   *  reason `hidden`), live, or refused (its reason says why). */
  type MetabrowserFileWatchState = "waiting" | "live" | "refused";
  type MetabrowserFileWatchListener = {
    onChange(change: MetabrowserFileChange): void;
    onState?(state: MetabrowserFileWatchState, reason: string | null): void;
  };
  type MetabrowserFileWatchOptions = MetabrowserFileWatchListener & {
    /** The generation the reader read, so a change before the watch is registered reaches it. */
    generation?: string | null;
  };
  type MetabrowserFileWatchRegistry = Readonly<{
    watch(
      path: string,
      listener: MetabrowserFileWatchListener,
      generation?: string | null,
    ): () => void;
    connected(id: string | null): void;
    hidden(now: boolean): void;
    changed(change: MetabrowserFileChange): void;
    describe(): ReadonlyArray<
      Readonly<{
        path: string;
        state: MetabrowserFileWatchState;
        reason: string | null;
        generation: string | null;
        listeners: number;
      }>
    >;
  }>;

  /** What static/event-reports.js reads: event_log_reports.browser_settings. */
  type MetabrowserEventReportSettings = {
    /** Whether the server writes an event log; without one nothing is tagged or sent. */
    log: boolean;
    /** When `log` is false, the server's own words for why, which Details shows. */
    off_reason?: string | null;
    route: string;
    header: string;
    slow_ms: number;
    freeze_ms: number;
    late_ms: number;
    flush_ms: number;
    max_batch: number;
    per_minute: number;
    long_lived: string[];
    failure_window_s: number;
    /** The command that opens the whole log in Metabrowser, which Details names. */
    open_command: string;
    /** The macOS app's menu item for it, which Details names instead when the app started the server. */
    open_menu: string | null;
  };

  type MetabrowserEventOutcome = "ok" | "failed" | "cancelled" | "never_completed";

  /** One report, as POST /api/event-log/client takes it. */
  type MetabrowserEventReport = {
    type: "fetch" | "render" | "wait";
    event: "open" | "end";
    name: string;
    client: string;
    dur_ms: number;
    outcome?: MetabrowserEventOutcome;
    attrs: {
      status?: number;
      server_ms?: number;
      threshold_ms?: number;
      error?: string;
      /** A wait the page spent some of hidden, and how long: time that is not late. */
      hidden?: boolean;
      hidden_ms?: number;
      detail?: Record<string, string | number | boolean | null>;
    };
  };

  type MetabrowserEventReportsEnvironment = {
    settings: MetabrowserEventReportSettings;
    /** The page's ID; a fresh one when absent. */
    pageId?: string;
    origin: string;
    path(): string;
    now(): number;
    setTimeout(callback: () => void, ms: number): unknown;
    clearTimeout(id: unknown): void;
    send(route: string, body: string): unknown;
    warn?(...args: unknown[]): void;
    /** Whether the page is hidden now; a wait's late timer runs only while it is shown. */
    hidden?(): boolean;
  };

  type MetabrowserEventWaitOptions = {
    /** When the wait began, on the page's clock, where it began before the reporter. */
    startedAt?: number;
    detail?: Record<string, string | number | boolean | null>;
    /** Told once, when the wait has run `late_ms` while the page was shown. */
    onLate?: (ms: number) => void;
  };

  type MetabrowserEventWait = Readonly<{
    startedAt: number;
    isLate(): boolean;
    end(outcome?: MetabrowserEventOutcome): void;
  }>;

  type MetabrowserEventReporter = Readonly<{
    page: string;
    settings: MetabrowserEventReportSettings;
    tag(url: string, method: string): { id: string; name: string } | null;
    started(request: { id: string; name: string }): void;
    settled(
      request: { id: string; name: string },
      result: { status?: number; serverTiming?: string | null; error?: { name?: string } | null },
    ): void;
    wait(name: string, options?: MetabrowserEventWaitOptions): MetabrowserEventWait;
    blocked(entry: {
      duration: number;
      startTime: number;
      blockingDuration?: number;
      scripts?: ReadonlyArray<{
        duration?: number;
        sourceFunctionName?: string;
        sourceURL?: string;
        invoker?: string;
      }>;
    }): void;
    earlier(
      entries: ReadonlyArray<{
        name: string;
        initiatorType: string;
        duration: number;
        responseStatus?: number;
        serverTiming?: ReadonlyArray<{ name: string; duration: number }>;
      }>,
    ): void;
    /** The page was hidden or shown: a wait's late timer stops while it is hidden. */
    visibility(hidden: boolean): void;
    leaving(): void;
    flush(): Promise<void>;
    queued(): MetabrowserEventReport[];
  }>;

  /** Which records the Details panel reads: a page's, and the failures in a window. */
  type MetabrowserEventDetailsQuery = {
    /** A page's ID, or one request's. */
    client?: string;
    /** UTC times to the second, as /api/event-log/failures takes them. */
    since?: string;
    until?: string;
  };

  type MetabrowserEventDetails = {
    /** `off`: this server writes no log, so whatever an older one wrote is not shown. */
    log: "present" | "absent" | "unreadable" | "off";
    /** With `off`, why this server writes no log, in its own words. */
    reason?: string | null;
    running: Array<{ kind: string; name: string; age_ms: number; mine: boolean }>;
    causes: Array<{
      cause: string;
      count: number;
      last: string;
      message: string;
      addresses: string[];
      examples: Array<{
        kind: string;
        name: string;
        outcome: string;
        dur_ms: number | null;
        ts: string;
      }>;
    }>;
    failures: number;
    since: string;
    probe: {
      target: string;
      verdict: string;
      ts: string;
      addresses: Array<{ address: string; result: string; ms: number | null }>;
    } | null;
    mine: Array<{
      event: string;
      kind: string;
      name: string;
      outcome: string | null;
      dur_ms: number | null;
      cause: string | null;
      ts: string;
    }>;
  };

  /** `mb.eventReports`: present once the `event-reports` bundle has loaded. */
  type MetabrowserEventReports = Readonly<{
    /** This page's ID, which every request it sends to /api/ is named under. */
    page: string;
    /** How long a wait runs before it is late. */
    lateMs: number;
    /** The window, in seconds, a failure's recent count covers. */
    failureWindowS: number;
    wait(name: string, options?: MetabrowserEventWaitOptions): MetabrowserEventWait;
    showDetails(
      panel: HTMLElement,
      query: MetabrowserEventDetailsQuery,
      options?: { signal?: AbortSignal },
    ): Promise<void>;
  }>;

  /** The shell's helpers view-header.js builds a header with, which app.js passes to it. */
  interface MetabrowserViewHeaderShell {
    esc(value: unknown): string;
    /** The served root, absolute. */
    servedRoot(): string;
    pathBaseName(path: string): string;
    /** The SDK's owner mark for the shell's delegated controls. */
    ownedControlAttr(): string;
    /** What a served mirror's page adds to its headings (mirror-heading.js). */
    mirrorHeading(part: "note"): string;
    /** A tree row's icon for a file name. */
    getFileIcon(name: string): { svg: string; cls: string; style: string };
    /** The name without a recognized compression suffix. */
    getLogicalName(entry: { name: string; compressed?: boolean; compression?: string }): string;
    sizeHtml(bytes: number | null | undefined, extraClass?: string): string;
    countHtml(n: number | null | undefined, extraClass?: string): string;
    formatAge(mtime: number | null, options?: { style?: "relative" }): string;
    /** The files whose writer the activity poll reports, which a run's status badge reads. */
    activeFiles: ReadonlyMap<string, unknown>;
  }
  /** What a file's view header reads from its `/api/file` envelope. */
  type MetabrowserViewHeaderFile = {
    path: string;
    compressed?: boolean;
    /** The compression's name, as `gzip`, where the file is compressed on disk. */
    compression?: string;
    size?: number | null;
    /** Epoch seconds; absent where the time could not be read. */
    mtime?: number | null;
    kind?: string;
    type?: string;
    /** A run's adapter, and whether and how the run ended. */
    summary?: { adapter?: string; is_done?: boolean; is_error?: boolean } | null;
    /** The YAML parser's message for a leading block it could not parse. */
    frontmatter_error?: string;
  };
  /** What a folder's view header reads from its folder envelope's `dir`. */
  type MetabrowserViewHeaderFolderTotals = Pick<
    MetabrowserFolderEnvelope["dir"],
    "mtime" | "not_indexed" | "total_files" | "total_size"
  >;
  /** What view-header.js builds: a file's and a folder's view header and their parts. */
  interface MetabrowserViewHeaderBuilders {
    folderHeaderSummaryHtml(dirInfo: MetabrowserViewHeaderFolderTotals): string;
    renderBadges(data: MetabrowserViewHeaderFile): string;
    renderFileHeader(data: MetabrowserViewHeaderFile): string;
    /** A Git tree's envelope has no `dir`. */
    renderFolderHeader(data: {
      path: string;
      dir?: MetabrowserViewHeaderFolderTotals | null;
    }): string;
    viewHeaderAgeHtml(mtime: number | null | undefined): string;
    viewHeaderEyebrowHtml(path: string): string;
    viewHeaderHtml(parts: MetabrowserViewHeaderParts): string;
    viewHeaderItemsHtml(items: string[]): string;
    viewHeaderName(path: string): string;
    viewHeaderUpHtml(path: string): string;
  }
  /** The parts of a view header, which view-header.js's viewHeaderHtml writes in its rows. */
  type MetabrowserViewHeaderParts = {
    /** Extra classes on the header, as `folder-header`. */
    className?: string;
    /** The item's path identity, written as the header's `data-path`. */
    path: string;
    /** The eyebrow's markup; an empty eyebrow is left out of the header's rhythm. */
    eyebrow: string;
    iconHtml: string;
    iconClass?: string;
    iconStyle?: string;
    title: string;
    /** The metadata line's markup. */
    line: string;
  };
  /** One exact source-text run and its validated Highlight.js classes. */
  interface MetabrowserSyntaxTokenRun {
    classes: string[];
    text: string;
  }

  /** Highlighted source split into one token-run array per source line. */
  type MetabrowserSyntaxTokenLines = MetabrowserSyntaxTokenRun[][];

  /**
   * Wire shapes for the `/api/git/` endpoints.
   *
   * These mirror the TypedDicts in `metabrowser/git/wire.py`, which is the
   * authority: that module also carries the runtime validators the server
   * tests run every emitted shape through. Keep the two in sync — a field
   * added on one side and not the other is exactly the drift the
   * validators exist to catch on the Python side and these types catch on
   * this side.
   */
  type MetabrowserGitRef = {
    /** Full refname, e.g. "refs/heads/main". Stable identity. */
    id: string;
    /** Short display name: "main", "<remote>/<branch>", "v1.0". */
    name: string;
    kind: "branch" | "remote" | "tag";
    revision: string;
    /** Present on the ref HEAD is currently on; never when detached. */
    is_head?: boolean;
    /** Present on the branch the repository merges into (main/master,
     * local or on a remote). Decided server-side. */
    is_trunk?: boolean;
    remote?: string;
  };

  type MetabrowserGitAuthor = {
    name?: string;
    email?: string;
  };

  type MetabrowserGitCommit = {
    id: string;
    short_id: string;
    /** Ordered; `[0]` is the first parent. The swimlane layout runs on this. */
    parent_ids: Array<string>;
    author?: MetabrowserGitAuthor;
    authored_at: number;
    committed_at: number;
    subject: string;
    refs?: Array<MetabrowserGitRef>;
  };

  type MetabrowserGitHead = {
    ref: string | null;
    revision: string | null;
    detached: boolean;
    unborn: boolean;
  };

  type MetabrowserGitRepoInfo = {
    is_repo: boolean;
    root?: string | null;
    head?: MetabrowserGitHead | null;
    reason?: string;
  };

  type MetabrowserGitHistorySummary = {
    is_repo: boolean;
    commit_count?: number;
    /** Committer date of the oldest root commit in scope; null when unborn. */
    first_commit_at?: number | null;
  };

  type MetabrowserGitLogPage = {
    is_repo: boolean;
    commits?: Array<MetabrowserGitCommit>;
    /** Opaque next-page token; null exactly when `has_more` is false. */
    cursor?: string | null;
    has_more?: boolean;
    /** Zero-based page within one bounded server history session. */
    page?: number;
    /** Replay token for this exact page. */
    page_cursor?: string;
    /** Replay token for the prior page; null on page zero. */
    previous_cursor?: string | null;
    scope?: "default" | "all";
    scope_refs?: Array<string>;
    scope_fingerprint?: string;
    graph_checkpoint?: {
      version: 1;
      prior_swimlanes: Array<MetabrowserGitGraphLane>;
      color_index: number;
      head_revision: string | null;
      scope_fingerprint: string;
    };
  };

  type MetabrowserGitGraphCheckpoint = {
    version: 1;
    priorSwimlanes: Array<MetabrowserGitGraphLane>;
    colorIndex: number;
    headRevision: string | null;
    scopeFingerprint: string;
  };

  type MetabrowserGitHistoryPage = {
    page: number;
    startOrdinal: number;
    commits: Array<MetabrowserGitCommit>;
    checkpoint: MetabrowserGitGraphCheckpoint;
    pageCursor: string;
    nextCursor: string | null;
    previousCursor: string | null;
    dispose?: () => void;
  };

  type MetabrowserGitHistoryPageCache = Readonly<{
    get(page: number): MetabrowserGitHistoryPage | null;
    peek(page: number): MetabrowserGitHistoryPage | null;
    put(page: MetabrowserGitHistoryPage): MetabrowserGitHistoryPage;
    remove(page: number): boolean;
    clear(): void;
    dispose(): void;
    readonly size: number;
    keys(): number[];
  }>;

  type MetabrowserGitHistoryWindowRange = Readonly<{
    start: number;
    end: number;
    visibleStart: number;
    visibleEnd: number;
    segmentStart: number;
    segmentEnd: number;
    segmentHeightPx: number;
    topSpacerPx: number;
    bottomSpacerPx: number;
    scrollTop: number;
    rebased: boolean;
  }>;

  type MetabrowserGitHistoryVirtualWindow = Readonly<{
    read(scrollTop: number, viewportHeight: number): MetabrowserGitHistoryWindowRange;
    setRowCount(rowCount: number): void;
    rebaseToOrdinal(
      ordinal: number,
      viewportHeight: number,
      align?: "nearest" | "start" | "center" | "end",
    ): number;
    dispose(): void;
    readonly rowCount: number;
    readonly segmentCapacity: number;
  }>;

  /** One answer of `GET /api/source/status`. */
  type MetabrowserSourceStatus = {
    subject: string;
    generation: number;
    pin: string | null;
    ref: string | null;
    ref_name: string | null;
    name: string | null;
    origin: string | null;
    location: string | null;
    refreshable: boolean;
    /** Whether the pin moves with its ref: a branch or tag, not a commit or pull request. */
    follows: boolean;
    latest: string | null;
    ref_on_origin: boolean | null;
    last_fetch_at: string | null;
    last_outcome: { operation: string; outcome: string; at: string } | null;
    refreshing: boolean;
    /**
     * Whether all that is refreshing is a fetch of the mirror no reader asked for, the
     * server's idle one or a visible page's once a window, which the row says nothing of.
     */
    refresh_quiet: boolean;
    stale: boolean;
    /**
     * How often, in seconds, a visible page of this pin makes its own ask, which has the
     * server probe the served branch at its origin; null for a pin that is not probed.
     */
    probe_every_s: number | null;
    pull_request: number | null;
    selection_state: "pending" | "found" | "not_found" | "fetch_failed" | "superseded" | null;
    selection_href: string | null;
    /** The checkout a mirror borrows objects from, beside `location`; null otherwise. */
    borrows: string | null;
    /** Whether the mirror's history stops at a shallow boundary. */
    shallow: boolean;
  };

  /** The pin and ref a page was rendered for. */
  type MetabrowserSourcePage = { pin: string; ref: string | null };

  type MetabrowserSourceOffer =
    | { kind: "switch"; ref: string; latest: string; text: string; commit: string; button: string }
    | { kind: "reload"; text: string; button: string }
    | { kind: "retry"; text: string; button: string };

  type MetabrowserPublicRepositoryContext = MetabrowserRepositoryContext;
  /** static/repository-links.js, the `repository-links` on-demand bundle. */
  type MetabrowserRepositoryLinkTarget =
    | Readonly<{
        kind: "view";
        target: MetabrowserNavigationTarget;
        localization: "revision" | "working-tree";
      }>
    | Readonly<{
        kind: "route";
        href: string;
        localization: "pull" | "commit" | "pulls";
        /** The pull request or stack a `pull` route opens, for a page that opens it in place. */
        pull: Readonly<{
          number: number;
          tab: "" | "files" | "checks" | "changes";
          file: string;
          stack: boolean;
        }> | null;
      }>
    | Readonly<{ kind: "external"; url: string }>;

  /** A pull request's text: the commit it describes and, when known, the files it changes. */
  type MetabrowserRepositoryTextContext = {
    head: string | null;
    changes?: { number: number; stack: boolean; files: ReadonlySet<string> };
  };

  type MetabrowserRepositoryLinksRuntime = Readonly<{
    /** The tooltip of a link that opens whatever revision is served. */
    WORKING_TREE_TITLE: string;
    localize(
      url: string,
      context: MetabrowserRepositoryContext | null | undefined,
      options?: {
        sourceKind?: "filesystem" | "git_revision";
        text?: MetabrowserRepositoryTextContext;
        pathRelative?: boolean;
        views?: boolean;
      },
    ): MetabrowserRepositoryLinkTarget | null;
    enhance(
      root: ParentNode,
      mb: Pick<MetabrowserPublicSdk, "navigation" | "repository" | "sourceKind">,
      options?: {
        text?: MetabrowserRepositoryTextContext;
        open?: (route: Extract<MetabrowserRepositoryLinkTarget, { kind: "route" }>) => boolean;
        views?: boolean;
      },
    ): number;
    fileUrl(
      context: MetabrowserRepositoryContext | null | undefined,
      revision: string,
      path: string[],
      directory?: boolean,
      suffix?: string,
    ): string | null;
    /** Whether a click is a plain primary one, which a link it made in-app opens in place. */
    isPlainClick(event: Event): boolean;
    viewFileUrl(
      context: MetabrowserRepositoryContext | null | undefined,
      revision: string,
      href: string,
    ): string | null;
  }>;

  /**
   * What a link with a link card opens (static/link-previews.js): a resolver's in-app
   * answer, or a rendered diff's link to a file of its head, a pin's `/view/<GitPath
   * wire>[#fragment]` address.
   */
  type MetabrowserLinkPreviewTarget =
    | Extract<MetabrowserRepositoryLinkTarget, { kind: "view" | "route" }>
    | Readonly<{ kind: "view-head"; href: string }>;

  /** What a link card is about, as `MetabrowserLinkPreviews.subject` reads a target. */
  type MetabrowserLinkPreviewSubject =
    | Readonly<{ kind: "pull"; number: number; tab: "" | "files" | "checks"; file: string }>
    | Readonly<{ kind: "stack"; number: number; file: string }>
    | Readonly<{ kind: "commit"; revision: string }>
    | Readonly<{
        kind: "file" | "folder";
        /** The path from the served root, decoded for display; "" for the root. */
        path: string;
        /** "working-tree" for a link to a branch, which opens whatever is served. */
        opens: "here" | "working-tree";
        /** The navigation target as the address spelled it: a view target's own, or a head
         *  link's GitPath wire path and decoded fragment. `card` does not read it. */
        target: MetabrowserNavigationTarget;
      }>
    | Readonly<{ kind: "pulls" }>;

  /** A provider's answer for a subject: plain text only, never markup. */
  type MetabrowserLinkPreview = Readonly<{
    title?: string;
    /** A pull request's state, which only its metadata can say. */
    state?: "open" | "closed" | "merged" | "draft";
    detail?: string;
    /** Said in place of where the link opens, as "Not in this repository". */
    missing?: string;
  }>;

  /** One kind's data for its link cards (`MetabrowserLinkPreviews.provide`). */
  type MetabrowserLinkPreviewProvider = Readonly<{
    summary(
      subject: MetabrowserLinkPreviewSubject,
      context: { mb: MetabrowserPublicSdk; signal: AbortSignal },
    ): Promise<MetabrowserLinkPreview | null> | MetabrowserLinkPreview | null;
    prefetch?(
      subject: MetabrowserLinkPreviewSubject,
      context: { mb: MetabrowserPublicSdk },
    ): unknown;
  }>;

  /** static/link-previews.js, in the `repository-links` on-demand bundle. */
  type MetabrowserLinkPreviewsRuntime = Readonly<{
    /** How long the pointer rests on a link before its summary and prefetch start. */
    INTENT_MS: number;
    register(
      root: Element,
      anchor: Element,
      target: MetabrowserLinkPreviewTarget,
      mb: MetabrowserPublicSdk,
      options?: { authorTitle?: string | null },
    ): boolean;
    forget(anchor: Element): void;
    dispose(root: Element): void;
    provide(
      kind: MetabrowserLinkPreviewSubject["kind"],
      provider: MetabrowserLinkPreviewProvider,
    ): void;
    subject(
      target: MetabrowserLinkPreviewTarget | null | undefined,
      sourceKind?: "filesystem" | "git_revision",
    ): MetabrowserLinkPreviewSubject | null;
    card(
      subject: MetabrowserLinkPreviewSubject,
      preview: MetabrowserLinkPreview | null | undefined,
      options?: { linkText?: string | null; authorTitle?: string | null },
    ): string;
  }>;

  /** What the freshness label says and offers; see static/source-freshness.js. */
  /** static/inert-html.js: untrusted Markdown reduced to an allowlist. */
  type MetabrowserInertHtmlRuntime = Readonly<{
    ALIGN_VALUES: Readonly<Record<string, readonly string[]>>;
    ALLOWED_ATTRIBUTES: Readonly<Record<string, readonly string[]>>;
    ALLOWED_TAGS: readonly string[];
    ANCHOR_PREFIX: string;
    CHECKBOX_ATTRIBUTES: ReadonlyArray<readonly [string, string]>;
    DIMENSIONS: Readonly<Record<string, readonly string[]>>;
    DROPPED_WITH_CONTENT: readonly string[];
    IMAGE_FALLBACK_CLASS: string;
    IMAGE_REFERRER_POLICY: string;
    blocksRemoteImages(): boolean;
    fragmentLink(href: string): string;
    headingSlug(text: string): string;
    allowedAttributes(
      tag: string,
      read: (name: string) => string | null,
      base: string | null,
    ): Array<[string, string]>;
    imageLink(
      src: string | null,
      alt: string | null,
      base: string | null,
    ): { href: string | null; text: string };
    isInside(href: string | null): boolean;
    keepsImage(src: string | null, base: string | null): boolean;
    linkHref(href: string | null, base: string | null): { href: string; leaves: boolean } | null;
    outsideLink(href: string | null, base: string | null): string | null;
    remoteImage(src: string | null, base: string | null): string | null;
    kpressProse(nodes: Node[], doc: Document): HTMLElement;
    sanitizeHtml(html: string, base: string | null, keepPathRelative?: boolean): Node[];
    sanitizeNodes(
      nodes: ArrayLike<Node>,
      doc: Pick<Document, "createElement" | "createTextNode">,
      base: string | null,
    ): Node[];
  }>;

  type MetabrowserSourceFreshnessModel = {
    visible: boolean;
    tone: "quiet" | "stale" | "refreshing" | "warning";
    label: string;
    detail: string;
    offer: MetabrowserSourceOffer | null;
    error: string | null;
    /** The attended pull request's page, when there is one. */
    pull: { href: string; text: string } | null;
    /** The branch or tag the page goes with to a new commit, which the controller does. */
    follow: MetabrowserSourceFollow | null;
  };

  /** A ref the page follows, and the commit it is at now. */
  type MetabrowserSourceFollow = { ref: string; commit: string };

  /**
   * What the commit view says about a commit the mirror lacks: being fetched, not
   * found, or not fetched because the fetch did not run; `retry` offers the fetch
   * again. `failed` is a commit route that failed, which says nothing about the commit.
   */
  type MetabrowserMissingCommitModel = {
    state: "pending" | "not_found" | "not_full" | "fetch_failed" | "failed";
    title: string;
    detail: string;
    retry: boolean;
  };

  /**
   * How asking for a missing commit's fetch ended: the status then, why it could not be
   * asked for or followed, whether a fetch of the mirror's branches and tags ran,
   * whether anything ran that could have brought the commit, and whether a full queue
   * refused the attended pull request's refresh, which alone brings a newer head of it.
   */
  type MetabrowserSourceFetchEnd = {
    status: MetabrowserSourceStatus | null;
    error: string | null;
    fetched: boolean;
    waited: boolean;
    pullRefused: boolean;
  };

  /** The commit view's side of opening a commit the mirror lacks. */
  type MetabrowserMissingCommitView = {
    /**
     * Ask the server for the commit again: `found` once it is painted, `missing` when
     * the server still does not have it, `failed` when the request itself failed.
     */
    load(): Promise<"found" | "missing" | "failed">;
    paint(model: MetabrowserMissingCommitModel): void;
    isCurrent(): boolean;
    now(): number;
  };

  type MetabrowserSourceResponse = { status: number; etag: string | null; body: unknown };

  type MetabrowserSourceFreshnessDependencies = {
    request(
      method: "GET" | "POST",
      route: string,
      options: { etag?: string | null; body?: unknown },
    ): Promise<MetabrowserSourceResponse>;
    schedule(callback: () => void, delayMs: number): unknown;
    cancel(handle: unknown): void;
    now(): number;
    isVisible(): boolean;
    render(model: MetabrowserSourceFreshnessModel): void;
    reload(): void;
    navigate(href: string): void;
    /** The page's own `/view/` address, or null on any other page. */
    address(): string | null;
  };

  type MetabrowserSourceFreshnessController = Readonly<{
    start(): Promise<void>;
    poll(): Promise<void>;
    requestRefresh(body?: Record<string, unknown>): Promise<string | null>;
    /** A reader's refresh, settled once nothing is fetching (static/refresh-plan.js). */
    refreshNow(): Promise<void>;
    fetchMissing(options?: {
      retry?: boolean;
      waiting?: () => void;
    }): Promise<MetabrowserSourceFetchEnd>;
    acceptOffer(): Promise<void>;
    onVisibilityChange(): void;
    dispose(): void;
    snapshot(): {
      status: MetabrowserSourceStatus | null;
      etag: string | null;
      shown: MetabrowserSourcePage | null;
      timerPending: boolean;
      refreshAskedWhileVisible: boolean;
      pageAskedWhileVisible: boolean;
      error: string | null;
    };
  }>;

  type MetabrowserSourceFreshnessRuntime = Readonly<{
    FAST_POLL_MS: number;
    SLOW_POLL_MS: number;
    createController(
      deps: MetabrowserSourceFreshnessDependencies,
      options?: { shown?: MetabrowserSourcePage | null },
    ): MetabrowserSourceFreshnessController;
    describe(
      status: MetabrowserSourceStatus | null,
      page: { shown: MetabrowserSourcePage | null; nowMs: number; error?: string | null },
    ): MetabrowserSourceFreshnessModel;
    describeMissingCommit(
      status: MetabrowserSourceStatus | null,
      page: {
        phase: "fetching" | "ended";
        nowMs: number;
        error?: string | null;
        fetched?: boolean;
        pullRefused?: boolean;
      },
    ): MetabrowserMissingCommitModel;
    mount(element: HTMLElement): MetabrowserSourceFreshnessController;
    openMissingCommit(
      controller: Pick<MetabrowserSourceFreshnessController, "fetchMissing">,
      view: MetabrowserMissingCommitView,
      options?: { retry?: boolean },
    ): Promise<"found" | "not_found" | "fetch_failed" | "failed" | "superseded">;
    relativeAge(iso: string | null, nowMs: number): string;
    selectionToOpen(
      status: MetabrowserSourceStatus | null,
      shown: MetabrowserSourcePage | null,
    ): string | null;
  }>;

  /** `remote` is a checkout's remote-tracking branches; a mirror has no such list. */
  type MetabrowserSourceRefKind = "branch" | "tag" | "remote";
  /** A list the chooser has a tab for: a kind of ref, or a checkout's working tree, which
   * is no ref and whose list answers only where its `HEAD` is. */
  type MetabrowserSourceListKind = MetabrowserSourceRefKind | "working_tree";

  /** One row of `GET /api/source/refs`. */
  type MetabrowserSourceRef = {
    name: string;
    ref: string;
    /** The commit's full ID, which the list shows as a short commit ID (`shortCommit`). */
    commit: string;
    /** When the commit was made, in epoch seconds; null when Git gives no date. */
    committed_at: number | null;
    default: boolean;
    /** The branch a checkout's `HEAD` is on; false on a mirror. */
    checked_out: boolean;
    current: boolean;
    /** The pull requests the branch is the head of, open first and then newest first;
     * absent when it is the head of none. */
    pulls?: MetabrowserSourceRefPull[];
    /** How many pull requests the branch heads, of which `pulls` lists the first few. */
    pulls_total?: number;
    /** On a row of the origin's branches read from Metabrowser's store, where the
     * checkout's own remote-tracking branch is when that is not this row's commit: its
     * commit and that commit's date, both null when the checkout has no such branch.
     * Absent where the two agree, and on every other row. */
    checkout?: { commit: string | null; committed_at: number | null };
  };

  /** A pull request as the ref list shows it: its state as the Pulls tab does. */
  type MetabrowserSourceRefPull = {
    number: number;
    title: string;
    state: "open" | "draft" | "merged" | "closed";
  };

  /** What a listing says of its rows' pull requests: whether the server has cached them. */
  type MetabrowserSourceRefPullRequests = {
    state: "absent" | "ready";
    /** Whether the cache holds every pull request, so a branch with none has none. */
    complete: boolean;
    /** Whether a job is filling it, so the list is worth asking for again. */
    refreshing: boolean;
  };

  /** One answer of `GET /api/source/refs`: every matching ref, the default or
   * checked-out branch first and then newest first. */
  type MetabrowserSourceRefListing = {
    kind: MetabrowserSourceListKind;
    query: string;
    /** The served commit and ref; both null while a checkout's working tree is served. */
    pin: string | null;
    ref: string | null;
    /** The lists the subject has, in the order of the chooser's tabs. */
    kinds: MetabrowserSourceListKind[];
    /** A checkout's working tree: whether it is served, the branch checked out or the
     * commit a detached `HEAD` is at, both read when the listing was made, and the
     * folder's name and its path with the home directory as `~`. Null on a mirror. */
    working_tree: {
      current: boolean;
      head: string | null;
      head_name: string | null;
      head_commit: string | null;
      name: string;
      location: string;
    } | null;
    /** Null where no provider has pull requests for the subject, and for tags. */
    pull_requests: MetabrowserSourceRefPullRequests | null;
    /** The store Metabrowser keeps of a checkout's origin, which its origin's branches and
     * tags are listed from once it is ready. Null or absent on a mirror, and for a checkout
     * that keeps none. */
    origin?: MetabrowserSourceRefOrigin | null;
    refs: MetabrowserSourceRef[];
  };

  /** What a listing says of the store of a checkout's origin (`OriginStore` in
   * metabrowser/checkout_store.py). */
  type MetabrowserSourceRefOrigin = {
    state: "ready" | "acquiring" | "absent";
    /** Why there is no store, as a code, and as a sentence for the page. */
    reason: string | null;
    detail: string | null;
    /** The origin as a page shows it. */
    address: string | null;
    last_fetch_at: string | null;
    last_outcome: { operation: string; outcome: string; at: string } | null;
    /** Whether a fetch of the store, or its first acquisition, runs now. */
    refreshing: boolean;
  };

  /** What the ref selector holds; see static/source-ref-selector.js. */
  type MetabrowserSourceRefSelectorState = {
    shown: MetabrowserSourcePage | null;
    open: boolean;
    kind: MetabrowserSourceListKind;
    query: string;
    listing: MetabrowserSourceRefListing | null;
    loading: boolean;
    switching: boolean;
    error: string | null;
    /** Whether the page is a checkout's; absent on a mirror's. */
    checkout?: boolean;
    /** The branch the checkout's HEAD is on, when it names one: as the page was drawn
     * with, and then as each listing says. */
    workingBranch?: string;
    /** The commit a detached HEAD is at, when HEAD names no branch. */
    workingCommit?: string;
    /** What the server came to serve instead of this page: a commit, "" for the working
     * tree, or null while the page is current. A checkout's page only. */
    stale?: string | null;
    /** The refs route said the folder is no repository's root: the row is removed. */
    removed?: boolean;
  };

  /** What the ref selector shows for one state. */
  type MetabrowserSourceRefSelectorModel = {
    selectedRef: { name: string; label: string; kind: string; ref?: string } | null;
    /** What the row says, as text: the ref, after "Working tree" and a dot on a
     * checkout's files on disk. */
    button: string;
    /** "Working tree", which a checkout's row starts with while the page shows its files
     * on disk; null on any page that shows a ref. */
    viewLabel: string | null;
    /** Those words' tooltip. */
    viewTip: string | null;
    /** The ref the row names, as text: "Branch: main", or "" for a working tree whose
     * HEAD could not be read. */
    refText: string;
    /** The served pull request's number, "#7", when the page is a pull request's head. */
    pullNumber: string | null;
    /** The served commit's ID, set in the commit-ID face, when the page is a bare commit's. */
    commitId: string | null;
    open: boolean;
    kind: MetabrowserSourceListKind;
    /** The tabs offered: a checkout's begin with its working tree, and its
     * remote-tracking branches are another. */
    kinds: MetabrowserSourceListKind[];
    query: string;
    /** What the filter box says and is named: it finds pull requests too once the server
     * has them. Null on the working tree's tab, which has no filter. */
    filterLabel: string | null;
    /** What the listing says of its pull requests; null with none. */
    pullRequests: MetabrowserSourceRefPullRequests | null;
    loading: boolean;
    switching: boolean;
    /** A checkout's working tree, the one entry of its tab: whether it is what the server
     * serves; the branch `HEAD` is on, or the short ID of the commit a detached one is at,
     * both null when it could not be read; and the folder's path, "" until the first
     * listing says it, with that path cut before the folder's own name, which the entry
     * keeps whole. Null on a mirror. */
    workingTree: {
      current: boolean;
      branch: string | null;
      commit: string | null;
      location: string;
      directory: string;
      base: string;
    } | null;
    rows: Array<{
      name: string;
      ref: string;
      /** The commit's ID as every line names one (`MetabrowserFormatters.shortCommit`). */
      commit: string;
      /** When the commit was made, in epoch seconds, which the row shows as an age. */
      committedAt: number | null;
      default: boolean;
      /** The branch a checkout's `HEAD` is on, badged "checked out". */
      checkedOut: boolean;
      current: boolean;
      /** The chip a row's name is drawn as. */
      chip: "local" | "remote" | "tag";
      /** What the row says where the reader's own `origin/<branch>` is not where the
       * origin's is: a short tag and the sentence its tooltip carries; else null. */
      own: { text: string; tip: string } | null;
      /** The pull requests the branch is the head of, the first of which the row shows. */
      pulls: MetabrowserSourceRefPull[];
      /** How many it heads, of which `pulls` lists the first few. */
      pullsTotal: number;
    }>;
    note: string;
    /** What the list says of the store a checkout's origin is listed from, and when that
     * store was fetched, which the line shows as an age; null where no list reads one. */
    origin: { text: string; fetchedAt: string | null; tone: "quiet" | "warning" } | null;
    error: string | null;
    /** What a checkout's page says once the server shows something else; else null. */
    stale: string | null;
    /** Whether the row is taken away: a folder Git does not take for a repository's root. */
    removed: boolean;
  };

  type MetabrowserSourceRefSelectorDependencies = {
    request(
      method: "GET" | "POST",
      route: string,
      body?: Record<string, string | boolean>,
      signal?: AbortSignal,
    ): Promise<MetabrowserSourceResponse>;
    schedule(callback: () => void, delayMs: number): unknown;
    cancel(handle: unknown): void;
    render(model: MetabrowserSourceRefSelectorModel): void;
    /** Go to *href*, or, with *state*, reload there as that history entry: the Commits tab's
     * landing, which has no address of its own. */
    navigate(href: string, state?: Readonly<{ gitLanding: true }>): void;
    /** The page's own pathname, sent so a switch can keep it. */
    currentView(): string | null;
    /** The main tab in front (`MAIN_TABS` in static/main-tabs.js), whose place a switch keeps. */
    tab?(): string | null;
    /** A switch is asked: *going* settles true when the page goes, false when it stays. */
    hold?(going: Promise<boolean>): boolean | undefined;
  };

  /** The elements the ref selector paints into. */
  type MetabrowserSourceRefSelectorParts = {
    /** Set when the selector is disposed, so a late load draws nothing. */
    disposed?: boolean;
    root: HTMLElement;
    toggle: HTMLButtonElement;
    label: HTMLElement;
    stale: HTMLElement;
    staleText: HTMLElement;
    reload: HTMLButtonElement;
    panel: HTMLElement;
    workingTree: HTMLButtonElement;
    /** Where `HEAD` is: the branch's chip, or a detached commit's ID. */
    workingTreeHead: HTMLElement;
    workingTreeDirectory: HTMLElement;
    workingTreeBase: HTMLElement;
    kinds: HTMLElement;
    tabs: Record<MetabrowserSourceListKind, HTMLButtonElement>;
    filter: HTMLInputElement;
    /** The list's scrolling box, whose rows are only those in its view (`drawWindow`). */
    list: HTMLElement;
    /** As tall as every row together, so the list scrolls over all of them. */
    sizer: HTMLElement;
    note: HTMLElement;
    origin: HTMLElement;
    error: HTMLElement;
    /** The rows the list shows now and which of them are drawn; see `drawWindow`. */
    rows: MetabrowserSourceRefSelectorRows;
  };

  /** The windowed list's state: every row the model shows, the drawn ones by index, the
   * row that takes Tab, and where each row sits, from the heights measured. Browser only. */
  type MetabrowserSourceRefSelectorRows = {
    shown: MetabrowserSourceRefSelectorModel["rows"];
    drawn: Map<number, HTMLLIElement>;
    roving: number;
    /** Each row's top and the last row's foot: one more entry than there are rows. */
    offsets: number[];
    /** The model the rows were last drawn from, for drawing them again. */
    model: MetabrowserSourceRefSelectorModel | null;
    /** Whether the GitHub plugin, which draws a pull request's state, was asked for. */
    iconsAsked: boolean;
    /** Set when every row is to be drawn again, though its refs are the same. */
    rebuild: boolean;
    /** The list and filter the rows are of, so a new one starts at its top. */
    listing: string;
    /** Whether this listing has been scrolled to the served ref's row, which it is once. */
    revealed: boolean;
    switching: boolean;
    choose: (ref: string) => void;
  };

  type MetabrowserSourceRefSelector = Readonly<{
    open(): Promise<void>;
    close(): void;
    toggle(): Promise<void>;
    /** Show another tab's list, as an arrow key along the tabs does; never switches. */
    setKind(kind: MetabrowserSourceListKind): Promise<void>;
    /** A press on a tab: on Working tree from a page that shows a ref, switch to the files
     * on disk; otherwise show the tab's list. */
    pressKind(kind: MetabrowserSourceListKind): Promise<void>;
    setQuery(query: string): void;
    choose(ref: string): Promise<void>;
    /** Show a checkout's working tree; does nothing on a mirror. */
    chooseWorkingTree(): Promise<void>;
    /** The checkout's `HEAD` moved: ask where it is and name it in place. */
    headChanged(): Promise<void>;
    /** Read an open list again, in place; a closed one reads when it next opens. */
    reread(): Promise<void>;
    /** Fetch the store of a checkout's origin, as the reader's Refresh asks; an open list
     * follows the fetch to its end. Does nothing on a mirror. */
    fetchOrigin(): Promise<void>;
    /** The server serves *served*, a commit or "" for the working tree, not this page. */
    servedChanged(served: string): void;
    dispose(): void;
    snapshot(): MetabrowserSourceRefSelectorState & { filterPending: boolean };
  }>;

  /** A mounted selector: its button, and the key's path, which opens the list and focuses its filter. */
  type MetabrowserSourceRefSelectorMount = MetabrowserSourceRefSelector &
    Readonly<{
      activate(): Promise<void>;
      button: HTMLButtonElement;
    }>;

  type MetabrowserSourceRefSelectorRuntime = Readonly<{
    FILTER_DELAY_MS: number;
    createSelector(
      deps: MetabrowserSourceRefSelectorDependencies,
      options?: {
        shown?: MetabrowserSourcePage | null;
        checkout?: boolean;
        workingBranch?: string;
        workingCommit?: string;
      },
    ): MetabrowserSourceRefSelector;
    describe(state: MetabrowserSourceRefSelectorState): MetabrowserSourceRefSelectorModel;
    mount(element: HTMLElement): MetabrowserSourceRefSelectorMount;
    /** The selector this page mounted, for the branch or tag key; null until it mounts. */
    mounted(): MetabrowserSourceRefSelectorMount | null;
    moveRow(key: string, index: number, count: number): number | null;
    /** The tab a list opens on: the one that holds what the page shows. */
    openKind(shown: MetabrowserSourcePage | null, checkout: boolean): MetabrowserSourceListKind;
    /** How often an open list asks again while the server fills its pull requests, in ms. */
    PULLS_POLL_MS: number;
    ROWS_OVERSCAN: number;
    /** Where a list scrolls to when its rows are laid out again, keeping the reader's place. */
    anchoredScroll(
      before: { refs: readonly string[]; offsets: readonly number[] },
      after: { refs: readonly string[]; offsets: readonly number[] },
      top: number,
      view: number,
      focused: string | null,
    ): number;
    /** Whether two answers of the refs route say the same. */
    sameListing(
      a: MetabrowserSourceRefListing | null,
      b: MetabrowserSourceRefListing | null,
    ): boolean;
    /** Whether two lists of rows are the same refs drawn the same way, whatever their pulls. */
    sameRefLines(
      a: ReadonlyArray<MetabrowserSourceRefSelectorModel["rows"][number]>,
      b: ReadonlyArray<MetabrowserSourceRefSelectorModel["rows"][number]>,
    ): boolean;
    /** Where each row sits, and where the last ends: one more entry than there are rows. */
    rowOffsets(
      rows: ReadonlyArray<{ pulls: ReadonlyArray<unknown> }>,
      plain: number,
      tall: number,
    ): number[];
    rowWindow(
      offsets: readonly number[],
      scrollTop: number,
      viewHeight: number,
      roving: number,
    ): { start: number; end: number; also: number };
    shownLabel(
      shown: MetabrowserSourcePage | null,
      checkout?: boolean,
    ): { kind: string; name: string };
  }>;

  type MetabrowserGitHistoryWindowRuntime = {
    classifyPageFailure(failure: {
      status: number;
      code: string | null;
      initial: boolean;
    }): "stale" | "recover" | "failed";
    createPageCache(options: {
      maxPages: number;
      onEvict?: (page: MetabrowserGitHistoryPage) => void;
    }): MetabrowserGitHistoryPageCache;
    createVirtualWindow(options: {
      rowHeight: number;
      maxRows: number;
      overscanRows: number;
      rebasePx: number;
    }): MetabrowserGitHistoryVirtualWindow;
  };

  type MetabrowserGitFileChange = {
    /** Served-root-relative unless `outside_root` is set. */
    path: string;
    old_path?: string;
    status: "added" | "modified" | "deleted" | "renamed" | "copied" | "typechanged";
    /** Null for binary files: git reports "-" rather than a line count. */
    additions: number | null;
    deletions: number | null;
    binary?: boolean;
    /** Inside the repository but outside the served root, so not navigable. */
    outside_root?: boolean;
    similarity?: number;
  };

  /**
   * Every count is null for a commit at a shallow boundary, whose changes are not known
   * here; the panel shows `?` for each, and the comparison says `parent_unavailable`.
   */
  type MetabrowserGitCommitStats = {
    files_changed: number | null;
    files_modified: number | null;
    files_added: number | null;
    files_deleted: number | null;
    additions: number | null;
    deletions: number | null;
  };

  /** A change's size, as `GET /api/git/commit-size/<rev>` answers it (git/wire.py,
   *  `GitChangeSize`): what Git pushes for it and its patch, uncompressed. */
  type MetabrowserGitChangeSize = {
    base: string | null;
    head: string;
    state: "measured" | "unknown";
    reason: string | null;
    commits: number | null;
    pushed_bytes: number | null;
    diff_bytes: number | null;
  };

  type MetabrowserGitCommitDetail = {
    is_repo: boolean;
    commit: MetabrowserGitCommit;
    body: string;
    stats: MetabrowserGitCommitStats;
    files: Array<MetabrowserGitFileChange>;
    files_truncated: boolean;
  };

  /** One lane in a row's graph gutter. */
  type MetabrowserGitGraphLane = {
    id: string;
    color: string;
  };

  type MetabrowserGitGraphRow = {
    commit: MetabrowserGitCommit;
    inputSwimlanes: Array<MetabrowserGitGraphLane>;
    outputSwimlanes: Array<MetabrowserGitGraphLane>;
    kind: "HEAD" | "node" | "incoming-changes" | "outgoing-changes";
  };

  type MetabrowserGitSwimlaneResult = {
    rows: Array<MetabrowserGitGraphRow>;
    /** Lane state after the last row; feed back in for the next page. */
    trailingSwimlanes: Array<MetabrowserGitGraphLane>;
    /** Palette cursor after the last row; feed back in for the next page. */
    colorIndex: number;
  };

  type MetabrowserGitGraphRuntime = {
    CIRCLE_RADIUS: number;
    CIRCLE_STROKE_WIDTH: number;
    HEAD_LANE_COLOR: string;
    LANE_COLORS: ReadonlyArray<string>;
    SWIMLANE_CURVE_RADIUS: number;
    SWIMLANE_HEIGHT: number;
    SWIMLANE_WIDTH: number;
    buildRefColors(headRefId: string | null): Map<string, string>;
    commitLaneIndex(row: MetabrowserGitGraphRow): number;
    computeSwimlanes(
      commits: Array<MetabrowserGitCommit>,
      options?: {
        priorSwimlanes?: Array<MetabrowserGitGraphLane>;
        colorIndex?: number;
        headRevision?: string | null;
        refColors?: Map<string, string>;
        rowStart?: number;
        rowEnd?: number;
      },
    ): MetabrowserGitSwimlaneResult;
    graphWidth(row: MetabrowserGitGraphRow): number;
    renderCommitGraph(row: MetabrowserGitGraphRow): SVGSVGElement;
  };

  /** A part of the page the navigation's Refresh refreshes (static/refresh-plan.js). */
  type MetabrowserRefreshPart = "source" | "refs" | "page" | "files" | "pulls" | "git" | "origin";

  /** What a module that owns a part lends the plan: its refresh, until released. */
  type MetabrowserRefreshParts = Readonly<{
    provide(id: MetabrowserRefreshPart, refresh: () => unknown): () => void;
  }>;

  type MetabrowserRefreshPlan = MetabrowserRefreshParts &
    Readonly<{
      press(): Promise<boolean>;
      waiting(): boolean;
      parts(): MetabrowserRefreshPart[];
    }>;

  type MetabrowserRefreshPlanRuntime = Readonly<{
    PARTS: readonly MetabrowserRefreshPart[];
    createPlan(deps: {
      shown(id: MetabrowserRefreshPart): boolean;
      waiting(on: boolean): void;
      failed?(id: MetabrowserRefreshPart, error: unknown): void;
    }): MetabrowserRefreshPlan;
    inVisibilityOrder(
      ids: readonly MetabrowserRefreshPart[],
      shown: (id: MetabrowserRefreshPart) => boolean,
    ): { visible: MetabrowserRefreshPart[]; hidden: MetabrowserRefreshPart[] };
    isShown(
      id: MetabrowserRefreshPart,
      view: { front: string; owner: string; chooser?: boolean },
    ): boolean;
    mount(): MetabrowserRefreshPlan | null;
    plan(): MetabrowserRefreshPlan | null;
  }>;

  /** A commit as a link's card names it (`MetabrowserGitPanel.commitSummary`): its subject,
   *  author, and commit time in seconds, or that the repository lacks it. */
  type MetabrowserGitCommitSummary =
    | { subject: string; author: string | null; committedAt: number | null; missing: false }
    | { subject: null; author: null; committedAt: null; missing: true };

  type MetabrowserGitPanelRuntime = {
    init(): Promise<void>;
    /** Read the history again once it has been read; settles when it is drawn. */
    refresh(): Promise<void>;
    /** Stops the panel's work for another owner; returns what disposes its shown commit diff. */
    cancelPending(): (() => void) | null;
    restoreCommitLanding(): Promise<void>;
    /** A commit's summary from the panel's own detail cache and missing set, null for a
     *  revision that is not a full commit ID or a read that failed. *signal* stops the
     *  caller waiting, never the read. It never fetches from origin. */
    commitSummary(
      revision: string,
      options?: { signal?: AbortSignal },
    ): Promise<MetabrowserGitCommitSummary | null>;
    /** Prepare a commit as a rest on its row does, for a rest on a link to it: nothing for a
     *  commit the repository lacks, and never in place of work still on its way. */
    prefetchCommit(revision: string): Promise<void>;
    /** Test-only surface; not part of any supported contract. */
    _internals: Record<string, unknown>;
  };

  /**
   * A nav-panel entry in the shell's tab bar.
   *
   * `onFirstShow` runs once, the first time the panel is shown — lazy
   * loading is the point, since a panel the user never opens should not
   * cost a request.
   */
  type MetabrowserNavPanel = {
    id: string;
    label: string;
    onFirstShow: (() => void) | null;
    onShow?: (() => void) | null;
    onHide?: (() => void) | null;
    /**
     * Focus the panel's roving row after its tab's letter opens it; false when the
     * panel has no row yet, and the tab button keeps focus.
     */
    focusRow?: (() => boolean) | null;
    /**
     * Reveal what the address names in this panel: open what holds it, select it, and
     * scroll it into view unless *scroll* is `keep` (main-tabs.js, `reveal`).
     */
    reveal?: ((how: MetabrowserRevealHow) => unknown) | null;
    /**
     * Home (main-tabs.js, `goHome`): put the panel back as a fresh load of `/view/` draws
     * it, from what it holds and with no read. A panel that keeps nothing across a switch
     * to it, as Commits, which lands on its newest commit every time, has none.
     */
    home?: (() => void) | null;
  };

  /** How the reader reached what the address names (main-tabs.js, `REVEAL_ROUTES`). */
  type MetabrowserRevealRoute = "open" | "address" | "history" | "nav" | "tab" | "step";
  type MetabrowserRevealHow = {
    scroll: "nearest" | "keep";
    isCurrent: () => boolean;
    /**
     * The reader opened the item already shown again (main-tabs.js, `reveal`): the call's
     * own intent, which no state keeps. Files reveals a file on every call, so only Pulls
     * reads it, to reveal the pull request the address already names.
     */
    again: boolean;
  };

  type MetabrowserMainTabsDeps = {
    cancelPreview(): void;
    flushPull(): void;
    /** The Files panel came to the front: what waited while it was hidden may run. */
    filesShown(): void;
    /** The Files panel left the front, its toolbar with it. */
    filesHidden(): void;
    /** Focus the Files tree's roving row: the Files panel's `focusRow`. */
    focusFilesRow(): boolean;
    isGitHistoryLanding(): boolean;
    isPullAddress(pathname: string): boolean;
    /** The reader's own open of the served root, `/view/`, drawn again at its default view. */
    openHome(): Promise<unknown>;
    /** The Files tab as a fresh load draws it: the Files panel's `home` (app.js, `resetFilesTab`). */
    resetFiles(): void;
    restore(): Promise<unknown>;
    /** Reveal the file the address names in the Files tree: the Files panel's `reveal`. */
    revealFile(how: MetabrowserRevealHow): Promise<unknown>;
    scrollShadow(): void;
  };
  type MetabrowserMainTabsController = {
    active(): string;
    activate(id: string): void;
    /** Bind the digits to a registry, or to none as the shell disposes it. */
    bindShortcuts(shortcuts: MetabrowserShortcutRegistry | null): void;
    finishGitDiscovery(): Promise<void>;
    /** Home: every tab forgets where it was, and the root opens at its default view. */
    home(): Promise<unknown>;
    /** The route of the Files landing the navigation controller applies, read once. */
    landingRoute(source: "startup" | "user" | "popstate"): MetabrowserRevealRoute;
    onHistory(): void;
    open(id: string): void;
    /** Open an address Pulls or Commits holds in place, as a link names it; see the SDK's. */
    openRoute(href: string): boolean;
    register(panel: MetabrowserNavPanel): void;
    remember(): void;
    remove(id: string): void;
    /** Show what the address names in its tab: switch to it and reveal the item there. */
    reveal(
      route: MetabrowserRevealRoute,
      how?: { isCurrent?: () => boolean; again?: boolean },
    ): Promise<void>;
  };

  type MetabrowserPreviewClaim = number;

  /**
   * The internal seam between the shell (static/app.js) and core modules that are not
   * file renderers. Deliberately narrow, and deliberately not `window.metabrowser`, which
   * is the documented plugin SDK and carries a compatibility contract: this is an internal
   * boundary that core modules loaded by the shell may use. Exposing it at all is what
   * lets git-panel.js stay out of app.js instead of adding a thousand lines to it.
   */
  type MetabrowserShellRuntime = {
    activateNavPanel(panelId: string): void;
    rememberMainTabAddress(): void;
    beginPreviewNavigation(claim: MetabrowserPreviewClaim): boolean;
    claimPreview(owner: string): MetabrowserPreviewClaim;
    endPreviewNavigation(claim: MetabrowserPreviewClaim): void;
    /** The address is the neutral Commits entry: `/view/` with no commit chosen. */
    isGitHistoryLanding(): boolean;
    isPreviewClaimCurrent(claim: MetabrowserPreviewClaim): boolean;
    openPullRequest(route: MetabrowserPullRoute): Promise<{ status: string }>;
    registerNavPanel(panel: MetabrowserNavPanel): void;
    removeNavPanel(panelId: string): void;
    renderPreviewHtml(html: string, claim: MetabrowserPreviewClaim): HTMLElement | null;
    renderPreviewNode(node: HTMLElement, claim: MetabrowserPreviewClaim): HTMLElement | null;
    /** Read the tree and the file or folder the pane holds again; settles when drawn. */
    rereadFiles(): Promise<unknown>;
    stagePreviewNode(node: HTMLElement, claim: MetabrowserPreviewClaim): (() => void) | null;
    shortcuts(): ReturnType<MetabrowserKeyboardShortcutsRuntime["create"]> | null;
    /** The page's freshness controller once it is mounted; null when a folder is served. */
    sourceFreshness(): Promise<MetabrowserSourceFreshnessController | null>;
  };
  type MetabrowserPublicKeyRevealApi = MetabrowserKeyRevealApi;
  type MetabrowserPublicShellKeymapApi = MetabrowserShellKeymapApi;
  type MetabrowserPublicShellKeymapShell = MetabrowserShellKeymapShell;
  type MetabrowserPublicNavCollapseController = MetabrowserNavCollapseController;
  type MetabrowserPublicTreeSection = MetabrowserTreeSection;
  type MetabrowserPublicGroupedLoad = MetabrowserGroupedLoad;
  type MetabrowserPublicShortcutRegistry = MetabrowserShortcutRegistry;
  type MetabrowserPublicShortcutTarget = MetabrowserShortcutTarget;
  type MetabrowserPublicShortcutCommand = MetabrowserShortcutCommand;
  type MetabrowserPublicPluginShortcutHandle = MetabrowserPluginShortcutHandle;
  type MetabrowserPublicPluginShortcutsApi = MetabrowserPluginShortcutsApi;
  type MetabrowserPublicQueuedShortcut = MetabrowserQueuedShortcut;
  type MetabrowserPublicFileTypeTaxonomyRuntime = MetabrowserFileTypeTaxonomyRuntime;
  type MetabrowserPublicFilterOption = MetabrowserFilterOption;
  type MetabrowserPublicTypeTallyRow = MetabrowserTypeTallyRow;
  type MetabrowserPublicTypeTally = MetabrowserTypeTally;
  type MetabrowserPublicTypeMenuOptions = MetabrowserTypeMenuOptions;
  type MetabrowserPublicTypePresetSection = MetabrowserTypePresetSection;
  type MetabrowserPublicPullRouteRuntime = MetabrowserPullRouteRuntime;
  type MetabrowserPublicPullStackNavigation = MetabrowserPullStackNavigation;
  type MetabrowserPublicPullsPanelHandle = MetabrowserPullsPanelHandle;
  type MetabrowserPublicPreparedViewComposition = MetabrowserPreparedViewComposition;
  type MetabrowserPublicRenderContext = MetabrowserRenderContext;
  /** One changed file, as a list of a change set's files gives it (static/changed-files-tree.js). */
  type MetabrowserChangedFileRow = {
    path: string;
    previous_path: string | null;
    status: string;
    additions: number | null;
    deletions: number | null;
    display: string;
    previous_display: string | null;
  };

  type MetabrowserChangedFilesFolder = {
    kind: "folder";
    id: string;
    name: string;
    files: number;
    additions: number | null;
    deletions: number | null;
    unknown: number;
    additionsUnknown: number;
    deletionsUnknown: number;
    children: MetabrowserChangedFilesNode[];
  };

  type MetabrowserChangedFilesNode =
    | MetabrowserChangedFilesFolder
    | { kind: "file"; id: string; name: string; row: MetabrowserChangedFileRow };

  type MetabrowserChangedFilesTreeModel = {
    root: MetabrowserChangedFilesFolder;
    files: number;
    folderIds: string[];
  };

  /** Which folders are open: `all` for a folder no reader touched, `toggled` by id. */
  type MetabrowserChangedFilesExpansion = {
    all: boolean;
    toggled: ReadonlyMap<string, boolean>;
  };

  type MetabrowserChangedFilesFolderRow = {
    kind: "folder";
    id: string;
    ids: string[];
    name: string;
    depth: number;
    position: number;
    setSize: number;
    expanded: boolean;
    files: number;
    additions: number | null;
    deletions: number | null;
    unknown: number;
    additionsUnknown: number;
    deletionsUnknown: number;
  };

  type MetabrowserChangedFilesFileRow = {
    kind: "file";
    id: string;
    name: string;
    depth: number;
    position: number;
    setSize: number;
    path: string;
    display: string;
    badge: string;
    status: string;
    statusLabel: string;
    additions: number | null;
    deletions: number | null;
    previousName: string | null;
    current: boolean;
  };

  type MetabrowserChangedFilesRow =
    | MetabrowserChangedFilesFolderRow
    | MetabrowserChangedFilesFileRow;

  /**
   * One part of a count summary (docs/design-system.md, "Count Summaries Bold Their
   * Numbers"): words as a string, in the line's ink and weight; a number as `{number}`,
   * painted bold (`.summary-number`); a list's punctuation, the comma between its entries,
   * as `{punctuation}`, and the " · " dot that sets a line's groups apart as `{separator}`,
   * both painted muted (`.summary-punctuation`), the separator hidden from assistive
   * technology, with `spoken`, what a screen reader is told in its place (`.visually-hidden`),
   * on a line whose name does not say it in words; and a status count, "21 A", as `{status,
   * letter, count}`, its count as written and its letter painted as one unit, both bold and
   * both in the status's ink (`.summary-status-count`, `.file-change-status`). The shell's
   * formatters.js paints them all, and a plugin through `metabrowser.countPartsNodes`.
   */
  type MetabrowserCountPart =
    | string
    | { readonly number: string; readonly sizeStyle?: "size" | "size size-large" }
    | { readonly punctuation: string }
    | { readonly separator: string; readonly spoken?: string }
    | { readonly status: string; readonly letter: string; readonly count: string };

  /**
   * A count summary in its parts, one shape for every count summary. "35 files changed" is
   * `[{number: "35"}, " files changed"]`, "2 A, 3 D" is `[{status: "added", letter: "A",
   * count: "2"}, {punctuation: ","}, " ", {status: "removed", letter: "D", count: "3"}]`,
   * and its text is the parts joined, a status count's as "2 A".
   */
  type MetabrowserCountParts = ReadonlyArray<MetabrowserCountPart>;

  /** A page's external counterpart, as `GET /api/counterpart` answers it. */
  type MetabrowserCounterpart = {
    /** Who hosts it, `github`; it names the markup's `data-view-on-<provider>` hooks. */
    provider: string;
    /** What its button says, "View on GitHub". */
    label: string;
    /** The counterpart's https URL. */
    url: string;
  };

  /** The served root's tracked and ignored files and bytes, the server's `summary` shape. */
  type MetabrowserRootTotals = {
    files: number;
    size: number;
    ignored_files: number;
    ignored_size: number;
  };

  /**
   * What a brief change line is built from (formatters.js, `changeLine`): the statuses in
   * the order shown, each with its letter, word, and count, null where not known, and the
   * line totals, null where not known.
   */
  type MetabrowserChangeLineInput = {
    statuses: ReadonlyArray<{ status: string; letter: string; word: string; count: number | null }>;
    additions: number | null;
    deletions: number | null;
  };

  /** A brief change line, "10 A, 5 D, 4 M · +1,234 −567" (docs/design-system.md). */
  type MetabrowserChangeLine = {
    /** "10 A, 5 D, 4 M", in a count summary's parts; none for no statuses. */
    statusParts: MetabrowserCountParts;
    /** "+1,234". */
    additions: string;
    /** "−567". */
    deletions: string;
    /** The line totals it shows, in order: each but a zero one, so none for a change of no
     *  lines, which it shows as "0 lines". */
    shownTotals: ReadonlyArray<"additions" | "deletions">;
    /** "10 A, 5 D, 4 M · +1,234 −567". */
    text: string;
    /** "10 added, 5 deleted, 4 modified; 1,234 lines added, 567 deleted". */
    label: string;
  };

  /**
   * What a change set's size line is built from (plugin-sdk-views.js, `changeSizeLine`): each count
   * null where not known and left out where `undefined`, and the sizes a change's size answer
   * gives (`pushed_bytes`, `diff_bytes`), the size group there once the pushed size is known.
   */
  type MetabrowserChangeSizeInput = {
    commits?: number | null;
    files: number | null;
    pushedBytes?: number | null;
    diffBytes?: number | null;
  };

  /** A change set's size line (docs/design-system.md, "Change Size Line"). */
  type MetabrowserChangeSizeLine = {
    /** The whole line in a count summary's parts. */
    parts: MetabrowserCountParts;
    /** "2.3 MB compressed (14.0 MB raw diff)", the last parts; none before the size is known. */
    sizeParts: MetabrowserCountParts;
    /** "77 commits · 83 files changed · 2.3 MB compressed (14.0 MB raw diff)". */
    text: string;
    /** "77 commits, 83 files changed, 2.3 MB compressed, 14.0 MB raw diff". */
    label: string;
    /** What each size is, for the size's tooltip; null before the size is known. */
    tooltip: string | null;
  };

  /** How a brief change line is painted where it stands. */
  type MetabrowserChangeLineOptions = {
    /** What a screen reader is told in the hidden dot's place, on a line with no name in words. */
    spoken?: string;
  };

  /** How a person's identity is drawn where it stands (plugin-sdk-views.js, `actorIdentity`). */
  type MetabrowserActorIdentityOptions = {
    /** The avatar's https address, which the caller vouches for; none draws the glyph. It is
     *  requested in anonymous CORS mode with no referrer, so its host must send
     *  `Access-Control-Allow-Origin`, and a folder served untrusted loads images only from
     *  `avatars.githubusercontent.com`; any other image shows the glyph. */
    avatar?: string | null;
    /** When the avatar loads: lazy, unless the placement is built again on a repaint. */
    loading?: "lazy" | "eager";
    /** Classes the placement adds to the identity's `span.actor-identity`. */
    className?: string;
    /** Classes the placement adds to the name's `strong.actor-name`. */
    nameClass?: string;
    /** False draws no box for a person with no avatar, as a dense list row does. */
    placeholder?: boolean;
  };

  type MetabrowserChangedFilesSummary = {
    /** "35 files changed", in its parts. */
    filesParts: MetabrowserCountParts;
    /** "2 A, 3 D, 30 M · +1,234 −3,423", the brief change line. */
    line: MetabrowserChangeLine;
    estimated: boolean;
    text: string;
    label: string;
  };

  /** static/changed-files-tree.js, the `changed-files-tree` on-demand bundle. */
  type MetabrowserChangedFilesTree = Readonly<{
    STATUS_BADGES: Readonly<Record<string, string>>;
    STATUS_LABELS: Readonly<Record<string, string>>;
    STATUS_WORDS: Readonly<Record<string, string>>;
    buildFileTree(rows: ReadonlyArray<MetabrowserChangedFileRow>): MetabrowserChangedFilesTreeModel;
    changeStats(
      row: { additions: number | null; deletions: number | null },
      formatCount: (count: number) => string,
    ): MetabrowserChangeLine | null;
    describeChanges(
      totals: { files: number; additions: number | null; deletions: number | null; exact: boolean },
      statuses: Iterable<string>,
      formatCount: (count: number) => string,
    ): MetabrowserChangedFilesSummary;
    /** A path as the server displays it: control, format, and invisible characters as U+FFFD. */
    displayPath(path: string): string;
    expansionFor(files: number, autoExpandFiles: number): MetabrowserChangedFilesExpansion;
    isOpen(expansion: MetabrowserChangedFilesExpansion, id: string): boolean;
    /** What a folder's sums leave out, in words, or "". */
    missingCounts(
      row: { kind: string; additionsUnknown?: number; deletionsUnknown?: number },
      formatCount: (count: number) => string,
    ): string;
    /** What a row is called, for a screen reader. */
    rowLabel(row: MetabrowserChangedFilesRow, formatCount: (count: number) => string): string;
    parentIndex(rows: ReadonlyArray<{ depth: number }>, at: number): number | null;
    revealPath(
      expansion: MetabrowserChangedFilesExpansion,
      path: string,
    ): MetabrowserChangedFilesExpansion;
    statusBreakdown(
      statuses: Iterable<string>,
    ): Array<{ status: string; count: number; word: string; letter: string }>;
    toggleFolder(
      expansion: MetabrowserChangedFilesExpansion,
      row: { ids: ReadonlyArray<string>; expanded: boolean },
    ): MetabrowserChangedFilesExpansion;
    visibleRows(
      tree: MetabrowserChangedFilesTreeModel,
      expansion: MetabrowserChangedFilesExpansion,
      options?: { current?: string | null },
    ): MetabrowserChangedFilesRow[];
    windowRange(where: {
      count: number;
      rowHeight: number;
      viewTop: number;
      viewBottom: number;
      listTop: number;
      overscan: number;
    }): { start: number; end: number };
  }>;

  type MetabrowserPublicSdk = MetabrowserSdk;
  type DiffFileDisclosure = DiffFileDisclosureShape;
  type MetabrowserPluginAssets = PluginAssets;
  type MetabrowserAgentLogRenderers = AgentLogRenderers;
  type MetabrowserGithubPullStateIcon = GithubExports["pullStateIcon"];
  type MetabrowserStructuredExports = StructuredExports;
  type MetabrowserStructuredTreeRow = StructuredTreeRow;
  type MetabrowserPublicViewDescriptor = MetabrowserViewDescriptor;
  type MetabrowserPublicViewSpec = MetabrowserViewSpec;

  var hljs: {
    getLanguage(language: string): unknown;
    registerLanguage(name: string, factory: () => Record<string, unknown>): void;
    highlight(
      source: string,
      options: { language: string; ignoreIllegals: boolean },
    ): { value: string };
    highlightElement(element: Element): void;
  };

  var Chart: new (
    canvas: HTMLCanvasElement,
    config: Record<string, unknown>,
  ) => MetabrowserChartInstance;

  interface Element {
    _metabrowserMount?: (() => void) | null;
  }

  interface Window {
    __structuredPreview?: StructuredPreviewGlobal;
    __structuredTree?: StructuredTreeGlobal;
    /** Set by the shell's prefetch chain once every optional asset has settled. */
    METABROWSER_OPTIONAL_ASSETS_SETTLED?: boolean;
    METABROWSER_ASSET_BUNDLES?: Record<
      string,
      Array<{ src: string; requires?: string; provides?: string }>
    >;
    /**
     * The root's immediate children, inlined by the shell so the tree can paint
     * before its first fetch returns. A snapshot from page-render time, painted
     * once and then replaced by the fetch; absent when the index was not warm
     * enough to answer at render time.
     */
    /** The root rows, and a landing path whose folders are inlined expanded. */
    METABROWSER_INITIAL_TREE?: {
      tree: TreeNode[];
      path?: string;
      /** The served root's tracked and ignored totals, once the walk has finished it. */
      summary?: { files: number; size: number; ignored_files: number; ignored_size: number };
    };
    MetabrowserAssets?: {
      ensureAsset(name: string): Promise<void>;
      assetLoaded(name: string): boolean;
      ensureModule(name: string): Promise<unknown>;
    };
    MetabrowserCharts?: MetabrowserChartRuntime;
    MetabrowserDocumentWidth: MetabrowserDocumentWidthRuntime;
    MetabrowserRemoteImages?: MetabrowserRemoteImagesRuntime;
    MetabrowserFileTypes?: {
      classFor(path: string): string;
      /** `style` carries the family colour as custom properties; "" when the
       * registry does not claim the extension. */
      iconFor(path: string): { cls: string; svg: string; style: string };
      styleFor(path: string): string;
      familyFor(path: string): string | null;
    };
    MetabrowserFileTypeTaxonomy: MetabrowserFileTypeTaxonomyRuntime;
    MetabrowserCatalogFeed: MetabrowserCatalogFeedRuntime;
    MetabrowserFileFuzzyMatch: MetabrowserFileFuzzyMatchRuntime;
    MetabrowserGitGraph: MetabrowserGitGraphRuntime;
    MetabrowserGitHistoryWindow: MetabrowserGitHistoryWindowRuntime;
    MetabrowserGitPanel?: MetabrowserGitPanelRuntime;
    MetabrowserIcons?: MetabrowserIconRegistry;
    MetabrowserKnownFileCatalog: MetabrowserKnownFileCatalogRuntime;
    MetabrowserKeyboardShortcuts: MetabrowserKeyboardShortcutsRuntime;
    MetabrowserKeyboardHelp: MetabrowserKeyboardHelpRuntime;
    MetabrowserKeyReveal?: MetabrowserKeyRevealRuntime;
    MetabrowserShellKeymap?: MetabrowserShellKeymapRuntime;
    MetabrowserPluginShortcuts?: MetabrowserPluginShortcutsRuntime;
    MetabrowserOverlay: MetabrowserOverlayRuntime;
    MetabrowserNavigationRoute: MetabrowserNavigationRouteRuntime;
    METABROWSER_PATH_ENCODING?: "utf16" | "bytes";
    MetabrowserPluginHost: MetabrowserPluginHostRuntime;
    MetabrowserContributionRegistry: MetabrowserContributionRegistryRuntime;
    MetabrowserFormatters: MetabrowserFormatterRuntime;
    MetabrowserInventoryScope: MetabrowserInventoryScopeRuntime;
    MetabrowserPendingTallyDiagnostics: MetabrowserPendingTallyDiagnosticsRuntime;
    MetabrowserRequestErrors: MetabrowserRequestErrorRuntime;
    MetabrowserResourceContext: MetabrowserResourceContextRuntime;
    MetabrowserSearch: MetabrowserSearchRuntime;
    MetabrowserShell?: MetabrowserShellRuntime;
    MetabrowserRefreshPlan?: MetabrowserRefreshPlanRuntime;
    MetabrowserMainTabs?: Readonly<{
      create(deps: MetabrowserMainTabsDeps): MetabrowserMainTabsController;
      /** The shell's controller's `openRoute`, false before the shell has made one. */
      openRoute(href: string): boolean;
      REVEAL_ROUTES: readonly MetabrowserRevealRoute[];
      landingRoute(
        source: "startup" | "user" | "popstate",
        pending: MetabrowserRevealRoute | null,
      ): MetabrowserRevealRoute;
      revealPlan(
        tab: string | null,
        route: MetabrowserRevealRoute,
        active: string,
      ): Readonly<{
        tab: string | null;
        switches: boolean;
        reveal: boolean;
        scroll: "nearest" | "keep";
      }>;
      tabAtAddress(
        address: { pathname: string; search: string; hash: string },
        how: {
          routes: MetabrowserNavigationRouteRuntime;
          isPullAddress: (pathname: string) => boolean;
          gitLanding: boolean;
        },
      ): string | null;
    }>;
    MetabrowserSearchPalette: MetabrowserSearchPaletteRuntime;
    MetabrowserTheme: MetabrowserThemeRuntime;
    MetabrowserNavCollapse?: MetabrowserNavCollapseRuntime;
    /** static/menus.js, a shell tool; the SDK's `menus` forwards to it. */
    MetabrowserMenus?: MetabrowserMenus;
    MetabrowserRevisionAges?: MetabrowserRevisionAgesRuntime;
    MetabrowserTreeExpansion: MetabrowserTreeExpansion;
    MetabrowserTreeFilterModel: MetabrowserTreeFilterModel;
    MetabrowserTreeKeyboardNavigation: MetabrowserTreeKeyboardRuntime;
    MetabrowserSourceAppend: MetabrowserSourceAppendRuntime;
    MetabrowserSourceLineAnchors?: MetabrowserSourceLineAnchorsRuntime;
    /** static/git-path.js, which only a pinned revision's shell loads. */
    MetabrowserGitPath?: Readonly<{
      display(path: string): string | null;
      text(path: string): string | null;
      wire(path: string | Uint8Array): string | null;
    }>;
    /** static/pull-route.js, the `pull-route` on-demand bundle. */
    MetabrowserPullRoute?: MetabrowserPullRouteRuntime;
    /** static/pulls-nav.js, which only a shell that drew the Pulls tab has. */
    MetabrowserPullsNav?: Readonly<{
      bindShortcuts(
        shortcuts: ReturnType<MetabrowserKeyboardShortcutsRuntime["create"]> | null,
      ): void;
      dispose(): void;
      init(): Promise<void>;
      routeChanged(options?: { preserveScroll?: boolean }): void;
    }>;
    MetabrowserSourceFreshness?: MetabrowserSourceFreshnessRuntime;
    /** static/event-reports.js, the `event-reports` on-demand bundle. */
    MetabrowserEventReports?: Readonly<{
      createReporter(env: MetabrowserEventReportsEnvironment): MetabrowserEventReporter;
      wrapFetch(fetchImpl: typeof fetch, reporter: MetabrowserEventReporter): typeof fetch;
      describeDetails(
        failures: unknown,
        pageLog: unknown,
        options: { slowMs: number; page?: string },
      ): MetabrowserEventDetails;
      detailLines(details: MetabrowserEventDetails): Array<{ heading: string; items: string[] }>;
      detailRoutes(query: MetabrowserEventDetailsQuery): { failures: string; page: string };
      showDetails(
        panel: HTMLElement,
        query: MetabrowserEventDetailsQuery,
        options?: {
          fetch?: typeof fetch;
          signal?: AbortSignal;
          slowMs?: number;
          log?: boolean;
          offReason?: string | null;
        },
      ): Promise<void>;
      serverMs(raw: string | null | undefined): number | null;
    }>;
    MetabrowserSourceRefSelector?: MetabrowserSourceRefSelectorRuntime;
    MetabrowserInertHtml?: MetabrowserInertHtmlRuntime;
    MetabrowserRepositoryLinks?: MetabrowserRepositoryLinksRuntime;
    /** static/link-previews.js, the link card, in the `repository-links` on-demand bundle. */
    MetabrowserLinkPreviews?: MetabrowserLinkPreviewsRuntime;
    /** static/changed-files-tree.js, the `changed-files-tree` on-demand bundle. */
    MetabrowserChangedFilesTree?: MetabrowserChangedFilesTree;
    MetabrowserSourcePinGuard?: Readonly<{
      hasChanged(): boolean;
      PIN_CHANGED_HEADER: string;
      PIN_HEADER: string;
      /** What the page of a checkout's working tree names in place of a commit. */
      WORKING_TREE_PIN: string;
      createHistoryGuard(
        deps: {
          status(): Promise<{ pin?: unknown } | null>;
          reload(): void;
        },
        pin: string | null,
      ): Readonly<{
        loaded(navigationType: string): Promise<void>;
        shown(persisted: boolean): Promise<void>;
        refused(): void;
        snapshot(): { asking: boolean; reloaded: boolean };
      }>;
      servesAnother(pin: string | null, served: { pin?: unknown } | null): boolean;
      shownPin(
        page: { pin?: unknown } | null | undefined,
        checkout: { working_tree?: unknown } | null | undefined,
      ): string | null | undefined;
      createSwitchHold(setTimer: (callback: () => void, ms: number) => void): Readonly<{
        hold(going: Promise<boolean>): void;
        release(): void;
        waiting(): Promise<void> | null;
      }>;
      guardFetch(
        fetchImpl: typeof fetch,
        pin: string,
        base: () => string,
        onPinChanged: (served: string) => void,
        waiting?: () => Promise<void> | null,
      ): typeof fetch;
      guardedRequest(url: string, base: string): boolean;
      /** This page's switch: its guarded requests wait until *going* says it stays, and
       * go with the page when it goes. False when another switch already holds the page. */
      hold(going: Promise<boolean>): boolean;
    }>;
    /** The pin and ref a pin's page was rendered for; absent on a folder. */
    METABROWSER_SOURCE_PIN?: MetabrowserSourcePage;
    /** Present on a checkout's page, a folder that is a repository's root: on its working
     * tree (`working_tree` true) and on each revision it shows. */
    METABROWSER_SOURCE_CHECKOUT?: { working_tree: boolean };
    /** The checkout's hosted origin for ref menus on its pinned revision pages. */
    METABROWSER_CHECKOUT_REF_CONTEXT?: MetabrowserRepositoryContext;
    /** The location note a mirror or pinned checkout carries in its view header. */
    MetabrowserMirrorHeading?: Readonly<{ note(): string }>;
    MetabrowserViewState: MetabrowserViewStateRuntime;
    MetabrowserViewComposition: MetabrowserViewCompositionRuntime;
    /** static/file-watches.js, the on-demand bundle `metabrowser.watchFile` fetches. */
    MetabrowserFileWatches?: Readonly<{
      createFileWatches(deps: {
        post(body: Record<string, unknown>): Promise<{ status: number; body: unknown }>;
        connection?: string | null;
        hidden?: boolean;
      }): MetabrowserFileWatchRegistry;
      createContainerFollower(deps: {
        watches: Pick<MetabrowserFileWatchRegistry, "watch">;
        setTimeout(callback: () => void, delayMs: number): ReturnType<typeof setTimeout>;
        clearTimeout(handle: ReturnType<typeof setTimeout>): void;
        observe(onMutation: () => void): () => void;
      }): Readonly<{
        follow(
          row: HTMLElement,
          children: HTMLElement,
          load: (row: HTMLElement, children: HTMLElement) => Promise<unknown>,
        ): void;
        sweep(): void;
        describe(): ReadonlyArray<Readonly<{ path: string; pending: boolean; running: boolean }>>;
      }>;
      shared(): MetabrowserFileWatchRegistry;
      followContainer(
        row: HTMLElement,
        children: HTMLElement,
        load: (row: HTMLElement, children: HTMLElement) => Promise<unknown>,
      ): void;
      connected(id: string | null): void;
      changed(change: MetabrowserFileChange): void;
    }>;
    /** The connection the page's /api/events stream named in its last snapshot (app.js). */
    metabrowserEventConnection?: string | null;
    /** static/view-header.js, an on-demand bundle loadViewComposition fetches. */
    MetabrowserViewHeader?: Readonly<{
      create(shell: MetabrowserViewHeaderShell): Readonly<MetabrowserViewHeaderBuilders>;
    }>;
    MetabrowserTreemapLayout: MetabrowserTreemapLayoutApi;
    MetabrowserTooltip?: {
      hide(within?: Element | null): void;
      show(html: string, anchor: Element | null): void;
    };
    METABROWSER_REPOSITORY_CONTEXT?: MetabrowserRepositoryContext | null;
    METABROWSER_SOURCE_KIND?: "filesystem" | "git_revision";
    /** The page's host's actions, defined frozen by the macOS app before any page script. */
    metabrowserHost?: Readonly<{ actions?: ReadonlyArray<unknown> }>;
    /** Whether the server's Git dates a revision's files, so its page offers Group by age and
     * Modified within (static/app.js `noFileAges`); set on a revision's page only. */
    METABROWSER_FILE_AGES?: boolean;
    /** Container kinds by extension; see arch-plugin-system.md. */
    METABROWSER_CONTAINER_EXTS?: Record<string, { kind: string; plugin: string; children: string }>;
    METABROWSER_SETTINGS?: {
      /** This build's tag, which a request names to be told its answer cannot change. */
      BUILD_TAG?: string;
      /** What the page reports to the event log, and when (static/event-reports.js). */
      EVENT_REPORTS?: MetabrowserEventReportSettings;
      /** The served store's token, named beside the build for the same reason; a folder has none. */
      STORE_TAG?: string;
      /**
       * The shell's reserved keys, from src/metabrowser/keymap.py: each key with the kinds
       * it is reserved for, or null for every kind. The plugin facade refuses them all.
       */
      RESERVED_SHELL_KEYS?: Readonly<Record<string, ReadonlyArray<string> | null>>;
      CAPABILITIES?: {
        active_content: boolean;
        mutations: boolean;
      };
      /**
       * The reader's privacy preference the page was served under: an untrusted document's
       * images from the web show as their alt text (static/remote-images.js).
       */
      BLOCK_REMOTE_IMAGES?: boolean;
      DOC_MAX_CHARS_DEFAULT?: number;
      /** Each family's distribution key with its color on each theme. */
      DISTRIBUTION_COLORS?: Array<{ key: string; light: string; dark: string }>;
      FILE_TYPE_REGISTRY?: {
        schema: "file-type-registry-v5";
        schema_version: 5;
        revision: number;
        fingerprint: string;
        max_extension_components: 2;
        groups: Array<{ id: string; label: string; order: number }>;
        families: Array<{
          id: string;
          label: string;
          group_id: string;
          order: number;
          extensions: Array<string>;
          hue: number;
          linguist: string | null;
          linguist_color: string | null;
          deviation: string | null;
          lightness_rank: number | null;
          chroma_ratio: number | null;
        }>;
        kinds: Array<{
          id: string;
          family_id: string | null;
          group_id: string;
          content_family: string;
          extensions: Array<string>;
          filenames: Array<string>;
          shebangs: Array<string>;
          priority: number;
        }>;
      };
      FILE_TYPE_GROUP_ORDER?: Array<string>;
      FILTER_TYPE_PRESETS?: Array<{
        id: string;
        label: string;
        values: Array<string>;
      }>;
      GIT_COMPARISON_CACHE_BYTES?: number;
      GIT_DETAIL_CACHE_SIZE?: number;
      GIT_HISTORY_PAGE_CACHE_PAGES?: number;
      GIT_HISTORY_SEGMENT_REBASE_PX?: number;
      GIT_HISTORY_WINDOW_MAX_ROWS?: number;
      GIT_HISTORY_WINDOW_OVERSCAN_ROWS?: number;
      GIT_HOVER_DEBOUNCE_MS?: number;
      /** How often a revision's page asks whether its files' ages have landed. */
      GIT_AGES_POLL_MS?: number;
      /** How long a page keeps asking for a read before it gives up, in milliseconds. */
      GIT_AGES_WATCH_GIVE_UP_MS?: number;
      GIT_LOG_LIMIT?: number;
      INDEX_PROGRESS_POLL_MS?: number;
      INDEX_PROGRESS_UPDATE_FILES?: number;
      PENDING_TALLY_DIAGNOSTIC_DELAY_MS?: number;
      PENDING_TALLY_DIAGNOSTIC_SAMPLE_LIMIT?: number;
      RECENT_CLUSTER_PCT?: number;
      RECENT_DEFAULT_WINDOW?: string;
      RECENT_LIMIT?: number;
      RECENT_RECLUSTER_DEBOUNCE_MS?: number;
      RECENT_WINDOW_SECONDS?: Record<string, number | null>;
      RECENT_WINDOWS?: Array<string>;
      ROLLUP_DEFAULT_DEPTH?: number;
      ROLLUP_DEFAULT_EXT_RANK?: "bytes" | "dual";
      ROLLUP_DEFAULT_EXT_TOP?: number;
      ROLLUP_FILE_TYPE_FILENAME_LIMIT?: number;
      ROLLUP_FILE_TYPE_REMAINING_LIMIT?: number;
      ROLLUP_DEFAULT_TOP?: number;
      ROLLUP_WATCH_DEBOUNCE_MS?: number;
      SYNTAX_HIGHLIGHT_MAX_BYTES?: number;
      TREE_AUTO_EXPAND_FALLBACK_ROWS?: number;
      TEXT_PREVIEW_CHUNK_BYTES?: number;
      TEXT_PREVIEW_MAX_CHUNK_BYTES?: number;
    };
    metabrowserDirectoryTotalsStore: MetabrowserDirectoryTotalsHostStore;
    metabrowser: MetabrowserSdk;
    metabrowserAgentLog?: {
      mountLogEventRaw?: (rawEl: HTMLElement) => void;
    };
    toggleKindFilter?: (kind: string) => void;
  }
}

export {};
