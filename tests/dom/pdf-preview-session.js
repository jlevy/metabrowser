// Browserless PDF-preview session using the production SDK, compositor, and renderer.
//
// It draws the view for each combination the plan's actions table names (host: the macOS
// app's descriptor or none; trust: active or inert), on a folder path and on a pinned
// revision's GitPath wire, and reads the SDK's `host` and `capabilities()` accessors the
// view decides by. Only the browser's painting of the PDF is left out.

const {
  APP_HOST,
  PDF_VIEW,
  createPage,
  describe,
  preparePdfView,
} = require("./pdf-view-harness.js");

const page = createPage();
const { document, sandbox } = page;

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function setProfile({ host, activeContent, sourceKind }) {
  page.serve({
    capabilities: { active_content: activeContent, mutations: false },
    sourceKind: sourceKind === "git_revision" ? "git_revision" : undefined,
    host,
  });
}

function describeMount(container) {
  const [bar, body] = container.children;
  return {
    actions: bar.children.map(describe),
    body: describe(body),
    childCount: container.children.length,
  };
}

(async () => {
  const sdk = sandbox.metabrowser;

  // The accessors the view decides by.
  setProfile({ host: null, activeContent: true });
  const browserHost = { actions: sdk.host.actions(), openFile: sdk.host.supports("open-file") };
  setProfile({ host: APP_HOST, activeContent: true });
  const appHost = { actions: sdk.host.actions(), openFile: sdk.host.supports("open-file") };
  setProfile({ host: { actions: "open-file" }, activeContent: true });
  const malformedHost = { actions: sdk.host.actions(), openFile: sdk.host.supports("open-file") };
  setProfile({ host: { actions: ["", 7, "reveal-file"] }, activeContent: true });
  const mixedHost = { actions: sdk.host.actions(), openFile: sdk.host.supports("open-file") };
  sandbox.METABROWSER_SETTINGS = {};
  const missingCapabilities = sdk.capabilities();
  setProfile({ host: null, activeContent: false });
  const inertCapabilities = sdk.capabilities();
  setProfile({ host: null, activeContent: true });
  const activeCapabilities = sdk.capabilities();
  const sdkAccessors = {
    capabilities: {
      active: activeCapabilities,
      frozen: Object.isFrozen(activeCapabilities),
      inert: inertCapabilities,
      missing: missingCapabilities,
    },
    host: { app: appHost, browser: browserHost, malformed: malformedHost, mixed: mixedHost },
  };

  // Composition: the renderer loads with the kind's assets, not eagerly.
  const composed = await preparePdfView(page, [PDF_VIEW]);
  const { assetRequests, prepared, renderer, lifecycle, host } = composed;
  assert(!composed.eagerlyRegistered, "pdf renderer was eager");
  assert(prepared.status === "ready", "pdf composition did not become ready");
  assert(renderer && typeof renderer.render === "function", "pdf preview did not register");

  const folderPath = 'papers/<unsafe "quoted" & file>.pdf';
  const gitWire = "g1-cGFwZXJz/g1-cmVwb3J0LnBkZg";

  async function mount(profile, filePath) {
    setProfile(profile);
    const { container, committed, status } = await composed.mount(filePath);
    return { container, result: { committed, status, ...describeMount(container) } };
  }

  const matrix = {};
  for (const [label, profile] of [
    ["appActive", { host: APP_HOST, activeContent: true }],
    ["appInert", { host: APP_HOST, activeContent: false }],
    ["browserActive", { host: null, activeContent: true }],
    ["browserInert", { host: null, activeContent: false }],
  ]) {
    matrix[label] = (await mount(profile, folderPath)).result;
  }
  const rendererInnerHtmlWrites = page.innerHtmlWrites();

  // A pinned revision is served inert, and its path is a GitPath wire.
  const pinned = await mount(
    { host: APP_HOST, activeContent: false, sourceKind: "git_revision" },
    gitWire,
  );
  const pinnedBrowser = await mount(
    { host: null, activeContent: false, sourceKind: "git_revision" },
    gitWire,
  );

  // Replacement and disposal: the active viewer releases its address when replaced.
  const first = await mount({ host: null, activeContent: true }, "first.pdf");
  const firstViewer = first.container.children[1];
  await mount({ host: null, activeContent: true }, "second.pdf");
  const replacement = {
    firstDetached: firstViewer.parentNode === null,
    firstReleasedSrc: !firstViewer.hasAttribute("src"),
    hostHoldsOne: host.children.length === 1,
  };
  const last = host.children[0];
  lifecycle.disposeActive();
  lifecycle.disposeActive();
  const disposal = { emptied: last.children.length === 0 };

  let threw = null;
  try {
    renderer.render(document.createElement("section"), { kind: "pdf", path: "" });
  } catch (error) {
    threw = error.message;
  }

  assert(appHost.openFile && !browserHost.openFile, "host.supports misread the descriptor");
  assert(!malformedHost.openFile, "a malformed descriptor was read as supporting open-file");
  assert(missingCapabilities.activeContent === false, "missing capabilities read as active");
  assert(matrix.appActive.body.tag === "embed", "app, active: no inline viewer");
  assert(matrix.browserInert.body.tag === "p", "browser, inert: an embed the policy blocks");
  assert(
    matrix.appActive.actions[0].attributes["data-metabrowser-open-file"] === "filesystem",
    "app Open link lost its marker",
  );
  assert(
    matrix.browserActive.actions.every((a) => !("data-metabrowser-open-file" in a.attributes)),
    "a browser was given the app's Open link",
  );
  assert(
    pinned.result.actions[0].attributes["data-metabrowser-open-file"] === "git_revision",
    "a pinned revision's Open link did not name its subject",
  );
  assert(rendererInnerHtmlWrites === 0, "pdf renderer constructed markup with innerHTML");
  assert(replacement.firstReleasedSrc && replacement.firstDetached, "replacement leaked a viewer");

  console.log(
    JSON.stringify(
      {
        composition: {
          assetRequests,
          initialView: prepared.initialView?.id,
        },
        disposal,
        emptyPathError: threw,
        innerHtmlWrites: rendererInnerHtmlWrites,
        matrix,
        pinned: { app: pinned.result, browser: pinnedBrowser.result },
        replacement,
        sdkAccessors,
      },
      null,
      2,
    ),
  );
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
