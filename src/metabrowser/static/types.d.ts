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

  type MetabrowserGitLogPage = {
    is_repo: boolean;
    commits?: Array<MetabrowserGitCommit>;
    /** Opaque; null exactly when `has_more` is false. */
    cursor?: string | null;
    has_more?: boolean;
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

  type MetabrowserGitCommitStats = {
    files_changed: number;
    additions: number;
    deletions: number;
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
      },
    ): MetabrowserGitSwimlaneResult;
    graphWidth(row: MetabrowserGitGraphRow): number;
    renderCommitGraph(row: MetabrowserGitGraphRow): SVGSVGElement;
  };

  type MetabrowserGitPanelRuntime = {
    init(): Promise<void>;
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
  };

  type MetabrowserPreviewClaim = number;

  /**
   * The internal seam between the shell and core modules that are not file
   * renderers. Deliberately not `window.metabrowser`, which is the
   * documented plugin SDK and carries a compatibility contract.
   */
  type MetabrowserShellRuntime = {
    activateNavPanel(panelId: string): void;
    claimPreview(owner: string): MetabrowserPreviewClaim;
    isPreviewClaimCurrent(claim: MetabrowserPreviewClaim): boolean;
    registerNavPanel(panel: MetabrowserNavPanel): void;
    removeNavPanel(panelId: string): void;
    renderPreviewHtml(html: string, claim: MetabrowserPreviewClaim): HTMLElement | null;
  };

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
    MetabrowserGitGraph: MetabrowserGitGraphRuntime;
    MetabrowserGitPanel?: MetabrowserGitPanelRuntime;
    MetabrowserIcons?: Record<string, string>;
    MetabrowserKnownFileCatalog: MetabrowserKnownFileCatalogRuntime;
    MetabrowserSearch: MetabrowserSearchRuntime;
    MetabrowserShell?: MetabrowserShellRuntime;
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
      GIT_DETAIL_CACHE_SIZE?: number;
      GIT_HISTORY_MAX_ROWS?: number;
      GIT_HOVER_DEBOUNCE_MS?: number;
      GIT_LOG_LIMIT?: number;
      INDEX_PROGRESS_POLL_MS?: number;
      INDEX_PROGRESS_UPDATE_FILES?: number;
      RECENT_CLUSTER_PCT?: number;
      RECENT_DEFAULT_WINDOW?: string;
      RECENT_LIMIT?: number;
      RECENT_RECLUSTER_DEBOUNCE_MS?: number;
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
