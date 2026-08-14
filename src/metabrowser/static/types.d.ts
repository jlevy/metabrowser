type MetabrowserRenderContext = {
  kind?: string;
  path?: string;
  raw?: unknown;
};

type MetabrowserViewSpec = {
  render: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  dispose?: (container: HTMLElement) => void;
};

type MetabrowserNavigationOpenOptions = {
  /** Activate this view when the destination declares it; otherwise use its default. */
  viewId?: string;
};

type MetabrowserNavigationApi = Readonly<{
  current(): MetabrowserNavigationTarget | null;
  href(target: MetabrowserNavigationTarget): string;
  open(
    target: MetabrowserNavigationTarget,
    options?: MetabrowserNavigationOpenOptions,
  ): Promise<void>;
}>;

type MetabrowserNavigationTarget = Readonly<{
  path: string;
  query?: string;
  fragment?: string;
}>;

type MetabrowserRepositoryContext = Readonly<{
  branch: string | null;
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
  start(): Promise<unknown>;
}>;

type MetabrowserNavigationRouteRuntime = Readonly<{
  attachController(controller: MetabrowserNavigationController): () => void;
  createController(options: {
    apply(
      target: MetabrowserNavigationTarget | null,
      context: MetabrowserNavigationApplyContext,
    ): unknown;
    eventTarget?: Pick<Window, "addEventListener" | "removeEventListener">;
    history?: Pick<History, "pushState" | "replaceState">;
    location?: Pick<Location, "pathname" | "search" | "hash">;
  }): MetabrowserNavigationController;
  href(target: MetabrowserNavigationTarget): string;
  navigation: MetabrowserNavigationApi;
  normalizeTarget(target: MetabrowserNavigationTarget): MetabrowserNavigationTarget;
  parse(pathname: string, search?: string, hash?: string): MetabrowserNavigationTarget | null;
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
};

type DisposableHandle = {
  dispose?: () => void;
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
  countClass(value: number): "" | "count-large";
  formatBytes(value: number): string;
  formatFileCount(value: number): string;
  formatInteger(value: number): string;
  sizeClass(value: number): "" | "size-large";
}>;

type MetabrowserFileTypeCategoryId = "docs" | "code" | "data";

type MetabrowserFileTypeCategory = Readonly<{
  id: MetabrowserFileTypeCategoryId;
  label: string;
  extraValues: ReadonlyArray<string>;
}>;

type MetabrowserFileTypeFamily = Readonly<{
  id: string;
  label: string;
  category: MetabrowserFileTypeCategoryId;
  extensions: ReadonlyArray<string>;
}>;

type MetabrowserFileTypeFamilyMatch = Readonly<{
  family: MetabrowserFileTypeFamily;
  canonicalExtension: string;
}>;

type MetabrowserFileTypeTaxonomyRuntime = Readonly<{
  categories: ReadonlyArray<MetabrowserFileTypeCategory>;
  families: ReadonlyArray<MetabrowserFileTypeFamily>;
  matchExtension(extension: unknown): MetabrowserFileTypeFamilyMatch | null;
  canonicalExtension(extension: unknown): string;
  categoryForFile(name: unknown, extension: unknown): MetabrowserFileTypeCategoryId | "other";
  distributionKeyForExtension(extension: unknown): string;
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
  setSlowThreshold?(milliseconds: number): number;
  snapshot?(): unknown;
};

type MetabrowserChartRuntime = {
  dispose(): void;
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
  label: string;
  title?: string;
  value: string;
};

type MetabrowserFilterSelection = string | Array<string> | null;

type MetabrowserFilterSnapshot = {
  recency: string;
  showIgnored: boolean;
  size: string;
  types: Array<string> | null;
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
  onMenuPick?: (key: string, value: string | null) => void;
  onMenuPreset?: (key: string, presetId: string, wasOn: boolean) => void;
  onMenuToggle?: (key: string, open: boolean) => void;
  onToggle?: (key: string, pressed: boolean) => void;
};

type MetabrowserFilterControls = {
  bind(root: Element, handlers: MetabrowserFilterHandlers): () => void;
  checkHtml(spec: {
    checked?: boolean;
    className?: string;
    key: string;
    label: string;
    title?: string;
  }): string;
  clearHtml(spec?: { className?: string; label?: string }): string;
  escapeHtml(value: unknown): string;
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
  menuGroupHtml(spec: {
    anyLabel: string;
    anyValue?: string;
    key: string;
    label: string;
    menuId: string;
    open?: boolean;
    options: Array<MetabrowserFilterOption>;
    presets?: Array<{
      count?: number;
      id: string;
      label: string;
      values: Array<string>;
    }>;
    select?: string;
    value: MetabrowserFilterSelection;
  }): string;
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
    title?: string;
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

type StructuredBuiltins = {
  calculateOptimalExpansion: (...args: Array<unknown>) => unknown;
  formatValue: (...args: Array<unknown>) => unknown;
  generateStructuredPreview: (...args: Array<unknown>) => unknown;
  materializeRows: (...args: Array<unknown>) => unknown;
  renderInlineTree(
    container: HTMLElement,
    data: unknown,
    options?: Record<string, unknown>,
  ): DisposableHandle | undefined;
  renderSource: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  renderTree: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
};

type AgentLogBuiltins = {
  disposeLog: (container?: HTMLElement) => void;
  renderCharts: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  renderLog: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  renderLogEvent: (container: HTMLElement, event: unknown, index: number) => string;
  renderRaw: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
};

type TextBuiltins = {
  renderSource: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
};

type MarkdownBuiltins = {
  mountRendered: (
    container: HTMLElement,
    ctx: MetabrowserRenderContext,
    options?: { signal?: AbortSignal },
  ) => DisposableHandle;
  renderSource: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
};

type MetabrowserBuiltins = {
  agentLog?: AgentLogBuiltins;
  markdown?: MarkdownBuiltins;
  structured?: StructuredBuiltins;
  text?: TextBuiltins;
  [name: string]: unknown;
};

type MetabrowserRollupEnvelope = {
  root: string;
  path: string;
  node: Record<string, unknown> | null;
  ext_tallies: Array<Array<unknown>>;
  type_tallies: {
    families: Array<{
      id: string;
      all_files: number;
      all_bytes: number;
      unignored_files: number;
      unignored_bytes: number;
      extensions: Array<[string, number, number, number, number]>;
    }>;
    extensions: Array<[string, number, number, number, number]>;
  };
  index_status: string;
  indexed_files: number;
  max_files: number;
  truncated: boolean;
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
    state: "pending" | "complete";
    total_files: number | null;
    total_size: number | null;
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
  classifyError?(error: unknown): FolderOverviewPanelError;
  label: string;
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

type MetabrowserAgeBucket = "sec" | "min" | "hr" | "day" | "wk" | "old";

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
  ageLabelHtml(mtimeSeconds: number | null | undefined): string;
  builtins: MetabrowserBuiltins;
  errors: MetabrowserRequestErrorRuntime;
  filters: MetabrowserFilterState;
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
  fetchRollup(path: string, opts?: Record<string, unknown>): Promise<MetabrowserRollupEnvelope>;
  fetchCompleteText(
    ctx: MetabrowserRenderContext,
    options?: { signal?: AbortSignal },
  ): Promise<string>;
  fileCatalog: MetabrowserPublicFileCatalogApi;
  fileTypes: MetabrowserFileTypeTaxonomyRuntime;
  fileTypeClass(path: string): string;
  fileTypeIcon(path: string): MetabrowserFileTypeIcon;
  formatTimestamp(secondsSinceEpoch: number): string;
  prefs: {
    get<T>(name: string, fallback: T): T;
    set(name: string, value: unknown): boolean;
  };
  tooltip: {
    hide(): void;
    move(event: MouseEvent): void;
    show(html: string, event: MouseEvent): void;
  };
  watchRollup(
    path: string,
    opts: Record<string, unknown>,
    onUpdate: (envelope: MetabrowserRollupEnvelope) => void,
  ): MetabrowserRollupWatch;
  fetchKpressRender(
    ctx: MetabrowserRenderContext,
    viewId?: string,
    options?: Record<string, unknown>,
  ): Promise<KpressRenderPayload>;
  fetchPluginData(
    plugin: string,
    endpoint: string,
    params: Record<string, unknown>,
  ): Promise<MetabrowserPluginData>;
  filterControls?: MetabrowserFilterControls;
  filterState?: MetabrowserFilterState;
  countClass(value: number): "" | "count-large";
  formatSize(value: number): string;
  formatFileCount(value: number): string;
  formatInteger(value: number): string;
  getRegisteredView(kind: string, view: string): MetabrowserViewSpec | undefined;
  icons: Record<string, string>;
  isLargeTextPreview(data: Record<string, unknown>): boolean;
  kpressInitToc(container: HTMLElement): (() => void) | null;
  langForExtension(ext: string): string;
  loadKpressAssets(manifest: KpressAssetManifest): Promise<void>;
  navigation: MetabrowserNavigationApi;
  repository: MetabrowserRepositoryContext | null;
  perf: MetabrowserPerf;
  registerView(kind: string, view: string, spec: MetabrowserViewSpec): void;
  setViewPrintState(
    container: HTMLElement,
    state: { printable: boolean; profile?: string; runtime?: string },
  ): void;
  renderTextTruncationWarning(data: Record<string, unknown>): string;
  sizeClass(value: number): "" | "size-large";
  sizeHtml(value: number | null | undefined, extraClass?: string): string;
  wrapWithCopy(html: string): string;
  viewState: Readonly<{
    isActive(container: HTMLElement): boolean;
    subscribeActive(container: HTMLElement, listener: (active: boolean) => void): () => void;
  }>;
};

type StructuredPreviewGlobal = {
  calculateOptimalExpansion: (...args: Array<unknown>) => unknown;
  formatValue: (...args: Array<unknown>) => unknown;
  generateStructuredPreview: (...args: Array<unknown>) => unknown;
};

type StructuredTreeGlobal = {
  materializeRows: (...args: Array<unknown>) => unknown;
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
  setFolderExpanded(row: HTMLElement, children: HTMLElement, expanded: boolean): void;
  toggleFolderExpanded(row: HTMLElement, children: HTMLElement): boolean;
  visibleRowBudget(viewportHeight: number, rowHeight: number, fallbackRows: number): number;
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

type MetabrowserKnownFileCatalogSnapshot = Readonly<{
  complete: boolean;
  files: ReadonlyArray<MetabrowserKnownFile>;
  observedCount: number;
  revision: number;
  sourceSummary: Readonly<Record<string, number>>;
}>;

type MetabrowserCatalogChangePayload = {
  upserts?: Array<{ p: string; e: string }>;
  removes?: string[];
};

type MetabrowserKnownFileCatalogApi = Readonly<{
  /**
   * @param bulkComplete the catalog is a complete view of the root (a finished
   *   walk that did not hit the max-files cap)
   * @param authoritative the payload lists every file the index holds, so
   *   feed-sourced paths it omits are stale and get retired. False for a
   *   payload built mid-walk, which is only a prefix.
   */
  applyBulkSnapshot(
    files: Array<{ p: string; e: string }>,
    bulkComplete: boolean,
    authoritative?: boolean,
  ): void;
  applyCatalogChange(payload: MetabrowserCatalogChangePayload): void;
  applyEventChange(
    ops: Array<{
      entry?: MetabrowserKnownFileCatalogWireEntry;
      op: string;
      path?: string;
    }>,
  ): void;
  clear(): void;
  markComplete(): void;
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
   * moved to, because projecting a snapshot per mutation would sort the whole
   * catalog on the hot path. Call `snapshot()` when the state is needed — that
   * also makes the value current rather than whatever held at notify time. A
   * listener that writes back does not re-enter.
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
}>;

type MetabrowserCatalogFeedApi = Readonly<{
  dispose(): void;
  onCatalogChange(payload: MetabrowserCatalogChangePayload): void;
  onIndexComplete(): void;
  onResync(): void;
  onSentinelSnapshot(): void;
  start(): void;
}>;

type MetabrowserCatalogFeedRuntime = Readonly<{
  create(options: {
    catalog: Pick<
      MetabrowserKnownFileCatalogApi,
      "applyBulkSnapshot" | "applyCatalogChange" | "markComplete"
    >;
    endpoint?: string;
    fetchImpl?: typeof fetch;
    scheduleRetry?: (callback: () => void, delayMs: number) => number;
    cancelRetry?: (handle: number) => void;
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
  target: "file";
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

type MetabrowserSearchBatch = Readonly<{
  candidateCount?: number;
  complete: boolean;
  providerId: string;
  results: ReadonlyArray<MetabrowserSearchFileResult>;
  revision?: number;
  statusMessage?: string;
  truncated: boolean;
}>;

type MetabrowserSearchContext = Readonly<{ requestId: number }>;

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
  results: ReadonlyArray<MetabrowserSearchFileResult>;
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
  createController(options?: { maxResults?: number }): MetabrowserSearchController;
  createLocalFileProvider(options: {
    catalog: MetabrowserKnownFileCatalogApi;
    chunkSize?: number;
    matcher: MetabrowserFileFuzzyMatchRuntime;
    maxResults?: number;
    syncThreshold?: number;
    yieldControl?: (signal: AbortSignal) => Promise<void>;
  }): MetabrowserSearchProvider;
}>;

type MetabrowserOpenFileOutcome = Readonly<{
  focusTarget?: HTMLElement | null;
  message?: string;
  status: "opened" | "not-found" | "error" | "cancelled";
}>;

type MetabrowserSearchPaletteApi = Readonly<{
  close(): void;
  dispose(): void;
  element: HTMLElement;
  isOpen(): boolean;
  open(): void;
}>;

type MetabrowserSearchPaletteRuntime = Readonly<{
  create(options: {
    controller: MetabrowserSearchController;
    document?: Document;
    getCatalogSnapshot(): { complete: boolean; observedCount: number };
    getFileIcon?(path: string): { cls?: string; svg?: string };
    maxRows?: number;
    onNotFound?(path: string): void | Promise<void>;
    openFile(path: string): MetabrowserOpenFileOutcome | Promise<MetabrowserOpenFileOutcome>;
    /**
     * Observe catalog growth so an open search converges instead of keeping
     * the coverage it had when the query ran. Returns an unsubscribe function.
     */
    subscribeCatalog?(listener: () => void): () => void;
  }): MetabrowserSearchPaletteApi;
}>;

declare global {
  type MetabrowserPublicFileTypeTaxonomyRuntime = MetabrowserFileTypeTaxonomyRuntime;
  type MetabrowserPublicRenderContext = MetabrowserRenderContext;
  type MetabrowserPublicSdk = MetabrowserSdk;

  var hljs: {
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
    MetabrowserCharts?: MetabrowserChartRuntime;
    MetabrowserDebug?: {
      clearFileCache(path?: string): void;
      selectFile(path: string): unknown;
    };
    MetabrowserFileTypes?: {
      classFor(path: string): string;
      iconFor(path: string): { cls: string; svg: string };
    };
    MetabrowserFileTypeTaxonomy: MetabrowserFileTypeTaxonomyRuntime;
    MetabrowserCatalogFeed: MetabrowserCatalogFeedRuntime;
    MetabrowserFileFuzzyMatch: MetabrowserFileFuzzyMatchRuntime;
    MetabrowserIcons?: Record<string, string>;
    MetabrowserKnownFileCatalog: MetabrowserKnownFileCatalogRuntime;
    MetabrowserNavigationRoute: MetabrowserNavigationRouteRuntime;
    MetabrowserPluginHost: MetabrowserPluginHostRuntime;
    MetabrowserContributionRegistry: MetabrowserContributionRegistryRuntime;
    MetabrowserFormatters: MetabrowserFormatterRuntime;
    MetabrowserInventoryScope: MetabrowserInventoryScopeRuntime;
    MetabrowserPendingTallyDiagnostics: MetabrowserPendingTallyDiagnosticsRuntime;
    MetabrowserRequestErrors: MetabrowserRequestErrorRuntime;
    MetabrowserResourceContext: MetabrowserResourceContextRuntime;
    MetabrowserSearch: MetabrowserSearchRuntime;
    MetabrowserSearchPalette: MetabrowserSearchPaletteRuntime;
    MetabrowserTheme: MetabrowserThemeRuntime;
    MetabrowserTreeExpansion: MetabrowserTreeExpansion;
    MetabrowserViewState: MetabrowserViewStateRuntime;
    MetabrowserTreemapLayout: MetabrowserTreemapLayoutApi;
    MetabrowserTooltip?: {
      hide(): void;
      move(event: MouseEvent): void;
      show(html: string, event: MouseEvent): void;
    };
    METABROWSER_REPOSITORY_CONTEXT?: MetabrowserRepositoryContext | null;
    METABROWSER_SETTINGS?: {
      FILE_TYPE_TAXONOMY?: {
        categories: Array<{
          id: MetabrowserFileTypeCategoryId;
          label: string;
          extra_values: Array<string>;
        }>;
        families: Array<{
          id: string;
          label: string;
          category: MetabrowserFileTypeCategoryId;
          extensions: Array<string>;
        }>;
      };
      FILTER_TYPE_PRESETS?: Array<{
        id: string;
        label: string;
        values: Array<string>;
      }>;
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
      ROLLUP_FILE_TYPE_NAMED_LIMIT?: number;
      ROLLUP_FILE_TYPE_RAW_LIMIT?: number;
      ROLLUP_DEFAULT_TOP?: number;
      ROLLUP_WATCH_DEBOUNCE_MS?: number;
      DISTRIBUTION_PALETTE_SLOTS?: number;
      TREE_AUTO_EXPAND_FALLBACK_ROWS?: number;
    };
    metabrowser: MetabrowserSdk;
    metabrowserAgentLog?: {
      mountLogEventRaw?: (rawEl: HTMLElement) => void;
    };
    metabrowserPerf?: MetabrowserPerf;
    toggleKindFilter?: (kind: string) => void;
  }
}

export {};
