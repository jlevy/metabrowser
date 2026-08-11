type MetabrowserRenderContext = {
  path?: string;
  raw?: unknown;
};

type MetabrowserViewSpec = {
  render: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  dispose?: () => void;
};

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
  disposeLog: () => void;
  renderCharts: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  renderLog: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  renderLogEvent: (container: HTMLElement, event: unknown) => unknown;
  renderRaw: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
};

type TextBuiltins = {
  renderSource: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
};

type MetabrowserBuiltins = {
  agentLog?: AgentLogBuiltins;
  markdown?: Record<string, unknown>;
  structured?: StructuredBuiltins;
  text?: TextBuiltins;
  [name: string]: unknown;
};

type MetabrowserSdk = {
  builtins: MetabrowserBuiltins;
  chart(
    container: HTMLElement | HTMLCanvasElement,
    type: string,
    data: Record<string, unknown>,
    options?: Record<string, unknown>,
  ): MetabrowserChartInstance;
  escapeHtml(value: string): string;
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
  formatSize(value: number): string;
  getRegisteredView(kind: string, view: string): MetabrowserViewSpec | undefined;
  icons: Record<string, string>;
  isLargeTextPreview(data: Record<string, unknown>): boolean;
  kpressInitToc(container: HTMLElement): () => void;
  langForExtension(ext: string): string;
  loadKpressAssets(manifest: KpressAssetManifest): Promise<void>;
  openPath(path: string): void;
  perf: MetabrowserPerf;
  registerView(kind: string, view: string, spec: MetabrowserViewSpec): void;
  renderTextTruncationWarning(data: Record<string, unknown>): string;
  wrapWithCopy(html: string): string;
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
  visibleRowBudget(viewportHeight: number, rowHeight: number, fallbackRows: number): number;
};

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
      iconFor(path: string): unknown;
    };
    MetabrowserCatalogFeed: MetabrowserCatalogFeedRuntime;
    MetabrowserFileFuzzyMatch: MetabrowserFileFuzzyMatchRuntime;
    MetabrowserIcons?: Record<string, string>;
    MetabrowserKnownFileCatalog: MetabrowserKnownFileCatalogRuntime;
    MetabrowserSearch: MetabrowserSearchRuntime;
    MetabrowserSearchPalette: MetabrowserSearchPaletteRuntime;
    MetabrowserTheme: MetabrowserThemeRuntime;
    MetabrowserTreeExpansion: MetabrowserTreeExpansion;
    MetabrowserTooltip?: {
      hide(): void;
      move(event: MouseEvent): void;
      show(html: string, event: MouseEvent): void;
    };
    METABROWSER_INITIAL_PATH?: string;
    METABROWSER_SETTINGS?: {
      FILTER_TYPE_PRESETS?: Array<{
        id: string;
        label: string;
        values: Array<string>;
      }>;
      INDEX_PROGRESS_POLL_MS?: number;
      INDEX_PROGRESS_UPDATE_FILES?: number;
      RECENT_CLUSTER_PCT?: number;
      RECENT_DEFAULT_WINDOW?: string;
      RECENT_LIMIT?: number;
      RECENT_RECLUSTER_DEBOUNCE_MS?: number;
      RECENT_WINDOW_SECONDS?: Record<string, number | null>;
      RECENT_WINDOWS?: Array<string>;
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
