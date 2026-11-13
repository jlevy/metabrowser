// The WKWebView probe's step attribution and scenario rows: which proxy requests belong
// to a step, and what one step's probe output and requests make of a scenario, with its
// refusals. No top-level effects, so tests/dom/wkprobe-run-behavior.mjs drives every
// refusal from synthetic probe output; wkprobe.mjs is the command line.
import { requestCounts } from "./wkprobe-stats.mjs";

export const VISIBLE = new Set(["cold", "reload", "relaunch"]);

/**
 * Proxy entries between a step's first start mark at or after `from` and its next end
 * mark, the times of both marks, and the index to search from for the next step.
 */
export function stepEntries(log, step, from) {
  const start = log.findIndex((e, i) => i >= from && e.mark === step && e.at === "start");
  if (start < 0) {
    return null;
  }
  const end = log.findIndex((e, i) => i > start && e.mark === step && e.at === "end");
  if (end < 0) {
    return null;
  }
  return {
    entries: log.slice(start + 1, end).filter((e) => !e.mark),
    startAt: log[start].t,
    endAt: log[end].t,
    next: end + 1,
  };
}

const present = (v) => v !== null && v !== undefined;

export function scenarioRow(name, stepOut, entries, ctx) {
  const facts = stepOut?.facts ?? {};
  const refusals = [];
  const { proxy, page } = requestCounts(entries, facts.resources);
  const screens = [stepOut?.screenBefore, stepOut?.screenAfter].filter(Boolean);
  for (const s of screens) {
    if (s.locked || s.displayAsleep || s.onConsole === false) {
      refusals.push([
        "screen",
        `locked ${s.locked}, display asleep ${s.displayAsleep}, on console ${s.onConsole}`,
      ]);
      break;
    }
  }
  if (!stepOut) {
    refusals.push(["probe", ctx.probeError ?? "the probe wrote no result for this step"]);
    return { name, refusals, proxy, page };
  }
  if (entries === null) {
    refusals.push(["marks", "the proxy did not log this step's start and end marks"]);
  }
  const vis = facts.vis ?? [];
  if (!(stepOut.raf >= 30)) {
    refusals.push(["raf", `${stepOut.raf} animation frames per second`]);
  }
  const out = { name, refusals };
  if (VISIBLE.has(name)) {
    if (vis.some(([, v]) => v !== "visible") || facts.visibility !== "visible") {
      refusals.push([
        "visibility",
        `visibility ${vis.map((v) => v[1]).join(",")} then ${facts.visibility}`,
      ]);
    }
    if (!present(stepOut.readyMs)) {
      refusals.push(["converged", "the subject never became ready"]);
    }
    Object.assign(out, {
      readyMs: stepOut.readyMs ?? null,
      mountedMs: stepOut.mountedMs ?? null,
    });
  } else {
    // The page clock's mark just before the show splits the visibility history: hidden
    // before it, and visible from the show to the end of the step.
    const chain = stepOut.showChain ?? null;
    const t0 = chain?.t0 ?? Number.POSITIVE_INFINITY;
    const before = vis.filter(([t]) => t < t0).map((v) => v[1]);
    const after = vis.filter(([t]) => t >= t0).map((v) => v[1]);
    if (
      stepOut.visibilityHidden !== "hidden" ||
      before.some((v) => v !== "hidden") ||
      stepOut.visibilityShown !== "visible" ||
      after.some((v) => v !== "visible") ||
      facts.visibility !== "visible"
    ) {
      refusals.push([
        "visibility",
        `hidden phase ${stepOut.visibilityHidden} (${before.join(",")}), shown ${stepOut.visibilityShown} (${after.join(",")}), at the end ${facts.visibility}`,
      ]);
    }
    const since = (v) => (present(v) && chain ? Math.round(v - chain.t0) : null);
    const painted = since(chain?.painted);
    if (painted === null) {
      refusals.push(["converged", "no painted frame with ready content after the show"]);
    }
    Object.assign(out, {
      hiddenMounted: present(stepOut.hiddenMountedMs),
      hiddenMountedMs: stepOut.hiddenMountedMs ?? null,
      hiddenReady: stepOut.hiddenReady === true,
      hiddenReadyMs: stepOut.hiddenReadyMs ?? null,
      showToPaintedReadyMs: painted,
      showToFirstFrameMs: since(chain?.firstFrame),
      showToReadyFrameMs: since(chain?.readyFrame),
      showToVisibleMs: stepOut.showToVisibleMs ?? null,
      showToPaintedReadyNativeMs: stepOut.showToPaintedReadyNativeMs ?? null,
      showFrames: chain ? { visible: chain.frames, hidden: chain.hiddenFrames } : null,
      rafHidden: stepOut.rafHidden,
    });
  }
  if (facts.version !== ctx.version) {
    refusals.push(["build_identity", `page reports ${facts.version}, expected ${ctx.version}`]);
  }
  if (facts.w !== ctx.viewport[0] || facts.h !== ctx.viewport[1]) {
    refusals.push(["viewport", `${facts.w}x${facts.h}, requested ${ctx.viewport.join("x")}`]);
  }
  if ((facts.errors ?? []).length) {
    refusals.push(["page_exceptions", facts.errors[0]]);
  }
  if ((facts.alerts ?? []).length) {
    refusals.push(["rendered_errors", facts.alerts[0]]);
  }
  return {
    ...out,
    commitMs: stepOut.commitMs ?? null,
    finishMs: stepOut.finishMs ?? null,
    raf: stepOut.raf,
    dpr: facts.dpr ?? null,
    navType: facts.navType ?? null,
    fcp: facts.fcp ?? null,
    dcl: facts.dcl ?? null,
    visibility: vis,
    screen: screens,
    proxy,
    page,
    // What the page says it loaded: path, initiator, transfer, encoded, and decoded bytes.
    resources: (facts.resources ?? [])
      .slice(0, 300)
      .map((r) => [r[0].slice(0, 100), r[2], r[3], r[4]]),
    requests: (entries ?? []).slice(0, 200).map((e) => ({
      m: e.method === "GET" ? undefined : e.method,
      u: e.url.slice(0, 120),
      st: e.status,
      c: e.inm || e.ims ? 1 : undefined,
    })),
  };
}

/** One run's device pixel ratio, or a refusal when its scenarios disagree. */
export function devicePixelRatioOf(scenarios) {
  const dprs = new Set(Object.values(scenarios).map((sc) => sc.dpr));
  if (dprs.size > 1) {
    return {
      ratio: [...dprs],
      refusal: ["viewport", `device pixel ratios ${[...dprs].join(", ")}`],
    };
  }
  return { ratio: dprs.size === 1 ? [...dprs][0] : null, refusal: null };
}
