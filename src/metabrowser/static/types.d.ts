type MetabrowserRenderContext = {
  path?: string;
  raw?: unknown;
};

type MetabrowserViewSpec = {
  render: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  dispose?: () => void;
};

type KpressRenderPayload = {
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
  renderPayload(container: HTMLElement, chartData: MetabrowserPluginData): unknown;
};

type MetabrowserChartInstance = {
  destroy(): void;
};

type LmdbKeyRow = {
  decoderUsed?: string;
  key?: string;
  subdb?: string;
  valuePreview?: string;
  valueSize?: number;
};

type LmdbStatsRow = {
  depth?: number;
  entries?: number;
  name?: string;
};

type MetabrowserPluginData = {
  keys?: Array<LmdbKeyRow>;
  nextCursor?: string;
  parse_error?: unknown;
  parsed?: unknown;
  pretty_yaml?: string;
  sizeBytes?: number;
  subdbs?: Array<LmdbStatsRow>;
  totalEntries?: number;
  truncated?: unknown;
  [key: string]: unknown;
};

type StructuredBuiltins = {
  calculateOptimalExpansion?: (...args: Array<unknown>) => unknown;
  formatValue?: (...args: Array<unknown>) => unknown;
  generateStructuredPreview?: (...args: Array<unknown>) => unknown;
  materializeRows?: (...args: Array<unknown>) => unknown;
  renderInlineTree(
    container: HTMLElement,
    data: unknown,
    options?: Record<string, unknown>,
  ): DisposableHandle | undefined;
  renderSource?: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  renderTree?: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
};

type AgentLogBuiltins = {
  renderCharts?: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  renderLog?: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
  renderLogEvent?: (container: HTMLElement, event: unknown) => unknown;
  renderRaw?: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
};

type TextBuiltins = {
  renderSource?: (container: HTMLElement, ctx: MetabrowserRenderContext) => unknown;
};

type MetabrowserBuiltins = {
  agentLog?: AgentLogBuiltins;
  lmdb?: Record<string, unknown>;
  markdown?: Record<string, unknown>;
  structured?: StructuredBuiltins;
  text?: TextBuiltins;
  [name: string]: unknown;
};

type MetabrowserSdk = {
  builtins?: MetabrowserBuiltins;
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
  formatSize?(value: number): string;
  icons: Record<string, string>;
  isLargeTextPreview(data: Record<string, unknown>): boolean;
  kpressInitToc(container: HTMLElement): () => void;
  langForExtension(ext: string): string;
  openPath(path: string): void;
  perf: MetabrowserPerf;
  registerView(kind: string, view: string, spec: MetabrowserViewSpec): void;
  renderTextTruncationWarning(data: Record<string, unknown>): string;
  wrapWithCopy(html: string): string;
};

type StructuredPreviewGlobal = {
  calculateOptimalExpansion?: (...args: Array<unknown>) => unknown;
  formatValue?: (...args: Array<unknown>) => unknown;
  generateStructuredPreview?: (...args: Array<unknown>) => unknown;
};

type StructuredTreeGlobal = {
  materializeRows?: (...args: Array<unknown>) => unknown;
  renderInlineTree: (
    container: HTMLElement,
    data: unknown,
    options?: Record<string, unknown>,
  ) => DisposableHandle | undefined;
};

declare global {
  var Chart: new (
    canvas: HTMLCanvasElement,
    config: Record<string, unknown>,
  ) => MetabrowserChartInstance;

  interface Window {
    __structuredPreview?: StructuredPreviewGlobal;
    __structuredTree?: StructuredTreeGlobal;
    MetabrowserCharts?: MetabrowserChartRuntime;
    MetabrowserIcons?: Record<string, string>;
    metabrowser?: MetabrowserSdk;
    metabrowserAgentLog?: {
      mountLogEventRaw?: (rawEl: HTMLElement) => void;
    };
    metabrowserPerf?: MetabrowserPerf;
    toggleKindFilter?: (kind: string) => void;
  }
}

export {};
