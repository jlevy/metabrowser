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
  destroy(): void;
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

type MarkdownBuiltins = {
  renderRendered: (container: HTMLElement, ctx: MetabrowserRenderContext) => Promise<void>;
  renderSource: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  disposeToc: () => void;
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
  index_status: string;
  indexed_files: number;
  max_files: number;
  truncated: boolean;
};

type MetabrowserRollupWatch = {
  refresh(): void;
  stale(): boolean;
  dispose(): void;
};

type MetabrowserAgeBucket = "sec" | "min" | "hr" | "day" | "wk" | "old";

type MetabrowserFilterStateValue = {
  current: boolean;
  ageWindow: "1h" | "24h" | "7d" | "30d" | null;
  types: string[] | null;
  ignored: "shown" | "dimmed" | "hidden";
};

type MetabrowserFilterRow = {
  mtime?: number | null;
  path?: string;
  active?: boolean;
  isDir?: boolean;
};

type MetabrowserFilterStateApi = {
  AGE_WINDOWS: string[];
  RECENT_DEFAULT_WINDOW: string;
  get(): MetabrowserFilterStateValue;
  set(patch: Partial<MetabrowserFilterStateValue>): void;
  clear(): void;
  subscribe(listener: (s: MetabrowserFilterStateValue) => void): () => void;
  activeCount(): number;
  windowSeconds(win: string): number;
  typeMatches(pathLike: string, types: string[] | null): boolean;
  rowMatches(row: MetabrowserFilterRow, s: MetabrowserFilterStateValue, nowSec: number): boolean;
};

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
  inner?: { x: number; y: number; w: number; h: number };
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
  focusTransform(
    focus: { x: number; y: number; w: number; h: number },
    viewport: { w: number; h: number },
  ): { scaleX: number; scaleY: number; translateX: number; translateY: number };
  projectRect(
    rect: { x: number; y: number; w: number; h: number },
    transform: { scaleX: number; scaleY: number; translateX: number; translateY: number },
  ): { x: number; y: number; w: number; h: number };
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
  escapeHtml(value: string): string;
  fetchRollup(path: string, opts?: Record<string, unknown>): Promise<MetabrowserRollupEnvelope>;
  fileTypeClass(path: string): string;
  formatTimestamp(secondsSinceEpoch: number): string;
  prefs: {
    get<T>(name: string, fallback: T): T;
    set(name: string, value: unknown): boolean;
  };
  filters: {
    get(): MetabrowserFilterStateValue;
    set(patch: Partial<MetabrowserFilterStateValue>): void;
    clear(): void;
    subscribe(listener: (s: MetabrowserFilterStateValue) => void): () => void;
    activeCount(): number;
    rowMatches(row: MetabrowserFilterRow, s: MetabrowserFilterStateValue, nowSec: number): boolean;
    typeMatches(pathLike: string, types: string[] | null): boolean;
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
    MetabrowserFilterState?: MetabrowserFilterStateApi;
    MetabrowserIcons?: Record<string, string>;
    MetabrowserTreeExpansion: MetabrowserTreeExpansion;
    MetabrowserTreemapLayout: MetabrowserTreemapLayoutApi;
    MetabrowserTooltip?: {
      hide(): void;
      move(event: MouseEvent): void;
      show(html: string, event: MouseEvent): void;
    };
    METABROWSER_SETTINGS?: {
      INDEX_PROGRESS_POLL_MS?: number;
      INDEX_PROGRESS_UPDATE_FILES?: number;
      RECENT_CLUSTER_PCT?: number;
      RECENT_DEFAULT_WINDOW?: string;
      RECENT_LIMIT?: number;
      RECENT_RECLUSTER_DEBOUNCE_MS?: number;
      RECENT_WINDOWS?: Array<string>;
      ROLLUP_DEFAULT_DEPTH?: number;
      ROLLUP_DEFAULT_EXT_TOP?: number;
      ROLLUP_DEFAULT_TOP?: number;
      ROLLUP_WATCH_DEBOUNCE_MS?: number;
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
