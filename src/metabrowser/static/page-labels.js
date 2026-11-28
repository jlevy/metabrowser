// Keep browser and native history labels on the route the main pane has actually shown.
// Loaded with the deferred shell tools. No renderer, fetch, or history entry of its own.

(() => {
  const preview = document.getElementById("preview-pane");
  if (!preview || window.MetabrowserPageLabels) {
    return;
  }

  const routes = window.MetabrowserNavigationRoute;
  const shellTitle = document.title;
  const fileHeader = ":scope > .view-header";
  const pullHeader = ":scope > .github-pull > .page-header > .github-pull-title";
  const commitStage = ":scope > .git-commit-stage";
  const stackOverview = "Stack Overview";
  const pullsList = "Pull requests";
  const rootIcons = new Map([
    ["folder", "folderDot"],
    ["git", "folderGit2"],
    ["mirror", "folderCloud"],
  ]);
  const pullIcons = new Map([
    ["draft", "gitPullRequestDraft"],
    ["closed", "gitPullRequestClosed"],
    ["merged", "gitMerge"],
  ]);
  const tabNames = new Map([
    ["conversation", "Conversation"],
    ["docs", "Docs"],
    ["files", "Changes"],
    ["changes", "Changes"],
    ["guided", "Guided Review"],
    ["checks", "Checks"],
  ]);
  const filters = new Map([
    ["open", "Open"],
    ["closed", "Closed"],
    ["all", "All"],
  ]);

  /** @param {string | null | undefined} text */
  function plainText(text) {
    // biome-ignore lint/suspicious/noControlCharactersInRegex: plain text for the window and menus
    return (text ?? "").replace(/[\s\u0000-\u001f\u007f]+/gu, " ").trim();
  }

  /** @param {string} text */
  function boundedBridgeText(text) {
    const bytes = new TextEncoder().encode(text);
    // A streaming decode omits a partial UTF-8 character at the boundary.
    return bytes.length <= 512
      ? text
      : new TextDecoder().decode(bytes.subarray(0, 512), { stream: true });
  }

  /** @param {string} path */
  function basename(path) {
    return routes.displayPath(path.split("/").at(-1) ?? "");
  }

  /** @param {...(string | null | undefined)} parts */
  function contextText(...parts) {
    return parts.filter(Boolean).join(" · ");
  }

  /** @param {string | undefined} fragment */
  function lineContext(fragment) {
    const anchors = window.MetabrowserSourceLineAnchors;
    const range = anchors?.parse(fragment);
    return range && anchors ? anchors.spoken({ ...range, status: "shown", message: "" }) : null;
  }

  /**
   * Each mounted heading must match the current address. A connected, inert stage and
   * the retained page it replaces can coexist while a read is in flight. Direct pane
   * selectors exclude the stage, and identity matching excludes the retained page.
   */
  function describe() {
    const { pathname, search, hash } = window.location;
    const target = routes.parse(pathname, search, hash);
    if (target) {
      if (!target.path && window.history.state?.gitLanding === true) {
        return {
          title: "Commits",
          icon: "gitCommit",
          committed: preview?.dataset.previewOwner === "git",
        };
      }
      const path = target.path.replace(/\/$/, "");
      const header = preview?.querySelector(fileHeader);
      const committed = header?.getAttribute("data-path") === path;
      const folder = committed
        ? header?.classList.contains("folder-header")
        : target.path.endsWith("/");
      const basenameContext = path.includes("/")
        ? routes.displayPath(path.slice(0, path.lastIndexOf("/")))
        : null;
      const view = window.MetabrowserSourceLineAnchors?.preferredView(target);
      const viewContext = view === "source" ? "Source" : view === "table" ? "Table" : null;
      const rootKind = document.getElementById("header-root-kind")?.dataset.rootKind;
      const rootIcon = rootIcons.get(rootKind ?? "") || "folder";
      const fileIcon = committed
        ? header?.querySelector(".view-header-icon")?.getAttribute("data-page-icon")
        : null;
      return {
        title:
          (committed ? header?.querySelector(".view-header-title")?.textContent : null) ||
          basename(path) ||
          shellTitle,
        icon:
          path === ""
            ? rootIcon
            : folder
              ? "folder"
              : fileIcon && Object.hasOwn(window.MetabrowserIcons ?? {}, fileIcon)
                ? fileIcon
                : "file",
        context: contextText(
          basenameContext,
          lineContext(target.fragment) ?? target.fragment ?? viewContext,
        ),
        committed,
      };
    }

    const pulls = window.MetabrowserPullRoute;
    const stack = pulls?.parseStack(pathname);
    const pull = pulls?.parsePull(pathname);
    const review = stack || pull;
    if (review) {
      const heading = preview?.querySelector(pullHeader);
      const host = heading?.parentElement?.parentElement;
      const number = `#${review.number}`;
      const committed =
        !!heading &&
        !host?.inert &&
        host?.classList.contains(stack ? "pull-stack-host" : "pull-request-host") &&
        heading.querySelector(".github-pull-number")?.textContent === number;
      const title = committed
        ? heading.querySelector(".github-pull-title-text")?.textContent
        : null;
      const state = heading?.querySelector(".github-pull-state-icon")?.getAttribute("data-state");
      return {
        title: title || (stack ? stackOverview : `Pull request ${number}`),
        icon: stack ? "layers" : pullIcons.get(state ?? "") || "gitPullRequest",
        context: contextText(title || stack ? number : null, tabNames.get(review.tab), review.file),
        committed,
      };
    }

    const list = pulls?.parsePulls(pathname, search);
    if (list) {
      return {
        title: pullsList,
        icon: "list",
        context: filters.get(list.state),
        committed: !!preview?.querySelector(":scope > .pull-request-list-host[data-preview-empty]"),
      };
    }

    const commit = routes.parseCommit(pathname);
    if (commit) {
      const stage = preview?.querySelector(commitStage);
      const committed = stage?.getAttribute("data-revision") === commit.revision;
      const short = committed
        ? stage?.querySelector(".git-commit-sha")?.textContent
        : window.MetabrowserFormatters.shortCommit(commit.revision);
      const title = committed ? stage?.querySelector("h1.git-commit-subject")?.textContent : null;
      return {
        title: title || `Commit ${short || commit.revision}`,
        icon: "gitCommit",
        context: contextText(title ? short : null, commit.file),
        committed,
      };
    }

    return { title: shellTitle, icon: "folder", committed: false };
  }

  let published = "";
  let observedHref = window.location.href;
  function publish() {
    const { title, icon, context, committed } = describe();
    const plainTitle = plainText(title) || shellTitle;
    if (document.title !== plainTitle) {
      document.title = plainTitle;
    }
    if (!committed || !window.metabrowserHost?.actions?.includes("navigation-history")) {
      return;
    }
    const bridge =
      /** @type {Window & {webkit?: {messageHandlers?: {metabrowserNavigation?: {postMessage: (label: unknown) => void}}}}} */ (
        window
      );
    const label = {
      kind: "label",
      url: window.location.href,
      title: boundedBridgeText(plainTitle),
      icon,
      context: boundedBridgeText(plainText(context)) || null,
    };
    const signature = JSON.stringify(label);
    if (signature !== published) {
      bridge.webkit?.messageHandlers?.metabrowserNavigation?.postMessage(label);
      published = signature;
    }
  }

  let queued = false;
  function addressChanged() {
    if (observedHref !== window.location.href) {
      observedHref = window.location.href;
      published = "";
    }
    if (!queued) {
      queued = true;
      queueMicrotask(() => {
        queued = false;
        publish();
      });
    }
  }

  /** Stop suppressing repeats when traversing, including between equal URLs. */
  function restore() {
    published = "";
    addressChanged();
  }

  // Most subtree work is body content (a diff, Markdown, a live log). Only changes
  // near an app-owned header, or the installation of a new pane, can change its identity.
  new MutationObserver((changes) => {
    if (
      changes.some(({ target }) => {
        const node = target instanceof Element ? target : target.parentElement;
        return (
          node === preview ||
          node?.matches(".view-header, .github-pull, .pull-request-list-host") === true ||
          !!node?.closest(
            ".view-header-title, .page-header.github-pull-header, .git-commit-subject",
          )
        );
      })
    ) {
      addressChanged();
    }
  }).observe(preview, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["data-preview-empty", "data-state", "data-page-icon", "data-preview-owner"],
  });

  window.addEventListener("popstate", restore);
  window.addEventListener("pageshow", restore);
  window.addEventListener("hashchange", addressChanged);
  window.addEventListener("metabrowser:navigation-fragment", addressChanged);
  window.MetabrowserPageLabels = Object.freeze({ addressChanged });
  publish();
})();
