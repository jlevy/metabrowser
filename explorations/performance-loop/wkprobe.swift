// WKWebView measurement probe for the Metabrowser performance loop.
//
// One process drives one real WKWebView through the steps of a job and writes what it
// saw as JSON. `wkprobe.mjs` compiles this file with swiftc, starts the server and the
// logging proxy, and runs the jobs; see README.md, "WKWebView Probe". Nothing here is
// product code, and there is no Xcode project, bundle, or signing: the wrapper embeds
// an Info.plist in the executable so WebKit files its data under one known identifier.
//
//   mb-wkprobe JOB_JSON
//
// A job names the page origin (the logging proxy), the path and subject to load, the
// website data store (`ephemeral`, a UUID for a persistent store, or `remove:UUID`),
// the window mode (`visible`, or `hidden`: created but never ordered in), and its steps:
//   load              load the path and wait for the exact subject to be ready
//   reload            WKWebView.reload() and wait again
//   hidden-load-show  load while hidden, record the hidden first view, then show the
//                     window and time show to the first painted frame with ready content
// Every step is bracketed by GET /__mark requests to the proxy, so the wrapper can
// attribute each logged request to its step.
import AppKit
import CoreGraphics
import WebKit

func nowMs() -> Double { ProcessInfo.processInfo.systemUptime * 1000 }
let processStart = nowMs()

// The host is an accessory app with no frontmost window, which makes it eligible for App
// Nap, and a napped process coalesces the main-thread timers that poll the page. The real
// app is frontmost at launch. The embedded Info.plist also sets LSAppNapIsDisabled; the
// display-sleep option keeps the display lit, so a long series is not refused for it.
let napGuard = ProcessInfo.processInfo.beginActivity(
  options: [.userInitiated, .latencyCritical, .idleDisplaySleepDisabled],
  reason: "wkprobe measurement")

struct Job: Decodable {
  let base: String
  let path: String
  let subject: String
  let store: String
  let window: String
  let steps: [String]
  let out: String
  let viewportWidth: Int
  let viewportHeight: Int
  let windowWidth: Int
  let windowHeight: Int
  let readyTimeoutMs: Double
  let settleMs: Double
  let hiddenWaitMs: Double
  // Diagnostic: wait this long after writing the result before exiting, to test whether
  // the relaunch depends on cache writes the first process had not flushed.
  let exitDelayMs: Double?
  // Exit when stdin reaches EOF, as it does when the wrapper holding its pipe dies.
  let lifeline: Bool?
}

/// Reads stdin on a thread of its own and exits the process at EOF, so a probe whose
/// wrapper was killed does not run on against a store or hold the display awake.
func watchLifeline() {
  Thread.detachNewThread {
    var buffer = [UInt8](repeating: 0, count: 256)
    while read(0, &buffer, buffer.count) > 0 {}
    FileHandle.standardError.write("wkprobe: stdin closed, exiting\n".data(using: .utf8)!)
    exit(3)
  }
}

/// Locked screen, a session that is not on the console, and a sleeping display all stop
/// WebKit from rendering a visible page, so each refuses a run.
func screenState() -> [String: Any] {
  var locked = false
  var onConsole = true
  if let d = CGSessionCopyCurrentDictionary() as? [String: Any] {
    if let v = d["CGSSessionScreenIsLocked"] as? Bool { locked = v }
    if let v = d["CGSSessionScreenIsLocked"] as? Int { locked = v != 0 }
    if let v = d[kCGSessionOnConsoleKey as String] as? Bool { onConsole = v }
  }
  let asleep = CGDisplayIsAsleep(CGMainDisplayID()) != 0
  return ["locked": locked, "onConsole": onConsole, "displayAsleep": asleep]
}

/// JSON-encode one string as a JavaScript string literal.
func jsString(_ s: String) -> String {
  let d = try? JSONSerialization.data(withJSONObject: [s], options: [])
  let a = d.flatMap { String(data: $0, encoding: .utf8) } ?? "[\"\"]"
  return String(a.dropFirst().dropLast())
}

// Installed at document start in every page: visibility changes, uncaught errors, and a
// Resource Timing buffer large enough for a cold landing.
let instrument = """
(() => {
  if (window.__wk) { return; }
  const W = (window.__wk = { vis: [[Math.round(performance.now()), document.visibilityState]], errors: [] });
  try { performance.setResourceTimingBufferSize(4000); } catch (e) {}
  document.addEventListener("visibilitychange", () => { W.vis.push([Math.round(performance.now()), document.visibilityState]); });
  window.addEventListener("error", (e) => { W.errors.push(String((e && e.message) || e).slice(0, 200)); });
  window.addEventListener("unhandledrejection", (e) => { W.errors.push("unhandled rejection: " + String(e.reason && (e.reason.message || e.reason)).slice(0, 200)); });
})();
"""

// Every load that would leave loopback is blocked, so a corpus with remote images or a
// script that reaches out cannot add network time or requests the proxy never sees.
// Content-blocker regexes have no alternation, hence one rule per allowed prefix.
let offlineRules = """
[{"trigger": {"url-filter": "^https?://"}, "action": {"type": "block"}},
 {"trigger": {"url-filter": "^wss?://"}, "action": {"type": "block"}},
 {"trigger": {"url-filter": "^https?://127\\\\.0\\\\.0\\\\.1[:/]"}, "action": {"type": "ignore-previous-rules"}},
 {"trigger": {"url-filter": "^wss?://127\\\\.0\\\\.0\\\\.1[:/]"}, "action": {"type": "ignore-previous-rules"}}]
"""

@MainActor
final class Probe: NSObject, WKNavigationDelegate {
  let job: Job
  var webView: WKWebView!
  var window: NSWindow!
  var commitAt = 0.0
  var finishAt = 0.0
  var terminations = 0
  var navigationErrors: [String] = []
  var steps: [[String: Any]] = []
  var rules: WKContentRuleList?
  var rulesState = "off"

  init(job: Job) { self.job = job }

  func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) { commitAt = nowMs() }
  func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { finishAt = nowMs() }
  func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
    navigationErrors.append("didFail: \(error.localizedDescription)")
  }
  func webView(
    _ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error
  ) {
    navigationErrors.append("didFailProvisionalNavigation: \(error.localizedDescription)")
  }
  func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { terminations += 1 }

  /// The page stays on the proxy's origin: a main-frame navigation anywhere else is
  /// cancelled and recorded, which refuses the run (`navigation`).
  func webView(
    _ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
    decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void
  ) {
    let url = action.request.url
    let isMain = action.targetFrame?.isMainFrame ?? true
    if !isMain || url?.scheme == "about" || sameOrigin(url) {
      decisionHandler(.allow)
      return
    }
    navigationErrors.append("blocked navigation to \(url?.absoluteString.prefix(120) ?? "nil")")
    decisionHandler(.cancel)
  }
  func sameOrigin(_ url: URL?) -> Bool {
    guard let url = url, let base = URL(string: job.base) else { return false }
    return url.scheme == base.scheme && url.host == base.host && url.port == base.port
  }

  func js(_ source: String) async -> Any? {
    await withCheckedContinuation { (c: CheckedContinuation<Any?, Never>) in
      webView.evaluateJavaScript(source) { value, error in
        if let error = error {
          c.resume(returning: "JSERR: \(error.localizedDescription)")
        } else {
          c.resume(returning: value)
        }
      }
    }
  }
  func jsJSON(_ expr: String) async -> Any? {
    guard let s = await js("JSON.stringify(\(expr))") as? String, let d = s.data(using: .utf8) else {
      return nil
    }
    return try? JSONSerialization.jsonObject(with: d, options: [.fragmentsAllowed])
  }
  func truthy(_ expr: String) async -> Bool {
    let v = await js("!!(\(expr))")
    if let b = v as? Bool { return b }
    if let n = v as? NSNumber { return n.boolValue }
    return false
  }
  /// Polls from the native side, so a hidden page's throttled timers cannot slow the
  /// clock that times it. Returns the elapsed time when true, or nil on timeout.
  func waitFor(_ expr: String, from t0: Double, timeoutMs: Double) async -> Double? {
    while nowMs() - t0 < timeoutMs {
      if await truthy(expr) { return nowMs() - t0 }
      try? await Task.sleep(nanoseconds: 10_000_000)
    }
    return nil
  }
  /// Polls several expressions in one evaluation per tick and records when each first
  /// became true, until every name in `until` has been seen or the timeout passes.
  /// Times are from `t0`.
  func watch(_ exprs: [(String, String)], from t0: Double, until: [String], timeoutMs: Double)
    async -> [String: Double]
  {
    var seen: [String: Double] = [:]
    // The outgoing document is marked before every load, so it can never satisfy a wait.
    let list = exprs.map { "!window.__wkOld && !!(\($0.1))" }.joined(separator: ", ")
    let start = nowMs()
    while nowMs() - start < timeoutMs {
      if let v = await js("[\(list)]") as? [Any] {
        for (i, e) in exprs.enumerated() where seen[e.0] == nil {
          let b = (v[i] as? Bool) ?? ((v[i] as? NSNumber)?.boolValue ?? false)
          if b { seen[e.0] = nowMs() - t0 }
        }
      }
      if until.allSatisfy({ seen[$0] != nil }) { break }
      try? await Task.sleep(nanoseconds: 10_000_000)
    }
    return seen
  }
  func sleepMs(_ ms: Double) async { try? await Task.sleep(nanoseconds: UInt64(ms * 1_000_000)) }
  func mark(_ step: String, _ at: String) async {
    guard let url = URL(string: "\(job.base)/__mark?step=\(step)&at=\(at)") else { return }
    _ = try? await URLSession.shared.data(from: url)
  }

  // A subset of the transition scenario's file-ready test: the route, the Files main tab,
  // the exact subject rendered in a laid-out active view with child content, the shared
  // pending modifier cleared, and no placeholder laid out in the active view. It does not
  // look for useful visible content, and it is a DOM state, not a painted frame.
  var readyExpr: String {
    """
    (() => { if (decodeURIComponent(location.pathname) !== \(jsString(job.path))) { return false; }
      const tab = document.querySelector(".nav-tab-bar .tab-btn.active"); if (!tab || tab.dataset.tab !== "files") { return false; }
      const p = document.getElementById("preview-pane"); if (!p || p.dataset.renderedPath !== \(jsString(job.subject))) { return false; }
      if (p.classList.contains("preview-navigation-pending") || p.getClientRects().length === 0) { return false; }
      const a = p.querySelector(':scope > [data-active-view="true"]');
      if (!a || a.childElementCount === 0 || a.getClientRects().length === 0) { return false; }
      return !Array.from(a.querySelectorAll(".loading, .mb-delayed-loading")).some((l) => l.getClientRects().length > 0); })()
    """
  }
  // Mounted does not depend on visibility: the subject rendered and the shell tools ready.
  var mountedExpr: String {
    """
    (() => { const p = document.getElementById("preview-pane");
      return !!p && p.dataset.renderedPath === \(jsString(job.subject)) && document.documentElement.dataset.shellToolsReady === "true"; })()
    """
  }
  let settledExpr =
    "document.documentElement.dataset.shellToolsReady === 'true' && window.METABROWSER_OPTIONAL_ASSETS_SETTLED === true"

  // Started just before the window is shown: an animation-frame chain that runs only once
  // the page is visible (a frame callback that runs while hidden is counted and skipped),
  // tests the ready predicate at the start of each frame, and stamps painted ready at the
  // start of the frame after the first one that began ready: the double-animation-frame
  // boundary of the transition scenarios. Times are on the page clock, from `t0`.
  var showChainJS: String {
    """
    (() => { const ready = () => (\(readyExpr));
      const S = (window.__wkShow = { t0: performance.now(), firstFrame: null, readyFrame: null, painted: null, frames: 0, hiddenFrames: 0 });
      const f = () => { const now = performance.now();
        if (document.visibilityState !== "visible") { S.hiddenFrames++; }
        else { S.frames++; if (S.firstFrame === null) { S.firstFrame = now; }
          if (S.readyFrame !== null) { S.painted = now; return; }
          if (ready()) { S.readyFrame = now; } }
        if (now - S.t0 < \(job.readyTimeoutMs)) { requestAnimationFrame(f); } };
      requestAnimationFrame(f); return true; })()
    """
  }

  let factsExpr = """
    (() => {
      const n = performance.getEntriesByType("navigation")[0] || {};
      const fcp = performance.getEntriesByName("first-contentful-paint")[0];
      const res = performance.getEntriesByType("resource").map((e) => [e.name.replace(location.origin, ""), e.initiatorType, Math.round(e.transferSize || 0), Math.round(e.encodedBodySize || 0), Math.round(e.decodedBodySize || 0), e.responseStatus || 0]);
      const alerts = Array.from(document.querySelectorAll('#preview-pane [role="alert"], #preview-pane .preview-error, #tree-content [role="alert"]')).filter((x) => x.getBoundingClientRect().height > 0).map((x) => (x.textContent || "").trim().slice(0, 160));
      const W = window.__wk || { vis: [], errors: [] };
      return { href: location.href, navType: n.type || null, navTransferSize: Math.round(n.transferSize || 0),
        responseStart: Math.round(n.responseStart || 0), dcl: Math.round(n.domContentLoadedEventEnd || 0), load: Math.round(n.loadEventEnd || 0),
        fcp: fcp ? Math.round(fcp.startTime) : null, resources: res, vis: W.vis, errors: W.errors, alerts,
        w: innerWidth, h: innerHeight, dpr: window.devicePixelRatio, version: ((document.querySelector(".menu-version") || {}).textContent || "").trim() || null,
        visibility: document.visibilityState, ua: navigator.userAgent };
    })()
    """

  func rafRate() async -> Any? {
    _ = await js(
      "window.__rafN = 0; window.__rafT = performance.now(); (function f() { window.__rafN++; if (performance.now() - window.__rafT < 500) { requestAnimationFrame(f); } })(); true"
    )
    await sleepMs(700)
    return await jsJSON("Math.round(window.__rafN * 1000 / 500)")
  }

  func compileRules() async {
    do {
      rules = try await WKContentRuleListStore.default().compileContentRuleList(
        forIdentifier: "wkprobe-offline", encodedContentRuleList: offlineRules)
      rulesState = rules == nil ? "error: no rule list" : "on"
    } catch {
      rulesState = "error: \(error.localizedDescription)"
    }
  }

  func makeWebView() -> Double {
    let t0 = nowMs()
    let config = WKWebViewConfiguration()
    if job.store == "ephemeral" {
      config.websiteDataStore = .nonPersistent()
    } else if let id = UUID(uuidString: job.store) {
      config.websiteDataStore = WKWebsiteDataStore(forIdentifier: id)
    }
    config.userContentController.addUserScript(
      WKUserScript(source: instrument, injectionTime: .atDocumentStart, forMainFrameOnly: true))
    if let rules = rules { config.userContentController.add(rules) }
    let viewport = NSRect(x: 0, y: 0, width: job.viewportWidth, height: job.viewportHeight)
    webView = WKWebView(frame: viewport, configuration: config)
    webView.navigationDelegate = self
    // A small, nearly transparent, click-through window holds a web view of the full
    // viewport size; the page lays out at the viewport and only a corner is drawn.
    let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
    let frame = NSRect(
      x: screen.minX + 8, y: screen.minY + 8, width: CGFloat(job.windowWidth),
      height: CGFloat(job.windowHeight))
    let w = NSWindow(contentRect: frame, styleMask: [.borderless], backing: .buffered, defer: false)
    let holder = NSView(frame: NSRect(origin: .zero, size: frame.size))
    webView.frame = NSRect(
      x: 0, y: CGFloat(job.windowHeight - job.viewportHeight), width: CGFloat(job.viewportWidth),
      height: CGFloat(job.viewportHeight))
    holder.addSubview(webView)
    w.contentView = holder
    w.isReleasedWhenClosed = false
    w.alphaValue = 0.02
    w.ignoresMouseEvents = true
    w.level = .floating
    w.hasShadow = false
    window = w
    if job.window == "visible" { w.orderFrontRegardless() }
    return nowMs() - t0
  }

  func load() {
    if let url = URL(string: job.base + job.path) { webView.load(URLRequest(url: url)) }
  }

  func step(_ name: String) async {
    let screen0 = screenState()
    await mark(name, "start")
    var row: [String: Any] = ["step": name, "screenBefore": screen0]
    commitAt = 0
    finishAt = 0
    _ = await js("window.__wkOld = true")
    let t0 = nowMs()
    if name == "reload" { webView.reload() } else { load() }
    let exprs = [("mounted", mountedExpr), ("ready", readyExpr)]
    if name == "hidden-load-show" {
      let hidden = await watch(exprs, from: t0, until: ["mounted"], timeoutMs: job.readyTimeoutMs)
      // Never mounting while hidden is an outcome, recorded as null, not a failure.
      row["hiddenMountedMs"] = hidden["mounted"].map { Int($0) } as Any
      // Whether the first view completes while hidden, given a fixed further wait.
      var readyHidden = hidden["ready"]
      if readyHidden == nil && hidden["mounted"] != nil {
        readyHidden = (await watch(exprs, from: t0, until: ["ready"], timeoutMs: job.hiddenWaitMs))[
          "ready"]
      }
      row["hiddenReady"] = readyHidden != nil
      row["hiddenReadyMs"] = readyHidden.map { Int($0) } as Any
      row["visibilityHidden"] = await js("document.visibilityState") as Any
      row["rafHidden"] = await rafRate() as Any
      _ = await js(showChainJS)
      let t1 = nowMs()
      window.orderFrontRegardless()
      // Only two reads that force no style or layout are polled here, so the probe puts
      // no layout of its own between the show and the painted frame. The chain's
      // `readyFrame` is the DOM ready after the show.
      let shown = await watch(
        [
          ("visible", "document.visibilityState === 'visible'"),
          ("painted", "!!window.__wkShow && window.__wkShow.painted !== null"),
        ], from: t1, until: ["visible", "painted"], timeoutMs: job.readyTimeoutMs)
      // The native clock's view of the same events: when a poll first saw each one.
      row["showToVisibleMs"] = shown["visible"].map { Int($0) } as Any
      row["showToPaintedReadyNativeMs"] = shown["painted"].map { Int($0) } as Any
      row["visibilityShown"] = await js("document.visibilityState") as Any
      row["showChain"] = await jsJSON("window.__wkShow || null") as Any
    } else {
      let seen = await watch(exprs, from: t0, until: ["mounted", "ready"], timeoutMs: job.readyTimeoutMs)
      row["readyMs"] = seen["ready"].map { Int($0) } as Any
      row["mountedMs"] = seen["mounted"].map { Int($0) } as Any
    }
    if commitAt > 0 { row["commitMs"] = Int(commitAt - t0) }
    _ = await waitFor(settledExpr, from: nowMs(), timeoutMs: 30000)
    await sleepMs(job.settleMs)
    if finishAt > 0 { row["finishMs"] = Int(finishAt - t0) }
    row["raf"] = await rafRate() as Any
    row["facts"] = await jsJSON(factsExpr) as Any
    await mark(name, "end")
    row["screenAfter"] = screenState()
    steps.append(row)
    FileHandle.standardError.write(
      "wkprobe \(name): ready \(row["readyMs"] ?? row["showToPaintedReadyNativeMs"] ?? "none") ms\n"
        .data(using: .utf8)!)
  }

  func run() async {
    var out: [String: Any] = ["job": job.store]
    if job.store.hasPrefix("remove:"), let id = UUID(uuidString: String(job.store.dropFirst(7))) {
      do {
        try await WKWebsiteDataStore.remove(forIdentifier: id)
        out["removed"] = true
      } catch {
        out["removed"] = false
        out["error"] = "\(error)"
      }
      write(out)
      return
    }
    let wk = Bundle(for: WKWebView.self).infoDictionary ?? [:]
    out["env"] = [
      "webkitVersion": wk["CFBundleVersion"] as? String ?? "",
      "webkitShortVersion": wk["CFBundleShortVersionString"] as? String ?? "",
      "os": ProcessInfo.processInfo.operatingSystemVersionString,
      "bundleIdentifier": Bundle.main.bundleIdentifier ?? "",
      "backingScale": Double(NSScreen.main?.backingScaleFactor ?? 0),
    ]
    out["screenAtStart"] = screenState()
    if !job.steps.isEmpty { await compileRules() }
    out["offlineRules"] = rulesState
    out["createWebViewMs"] = Int(makeWebView())
    out["launchToWebViewMs"] = Int(nowMs() - processStart)
    for s in job.steps { await step(s) }
    out["steps"] = steps
    out["terminations"] = terminations
    out["navigationErrors"] = navigationErrors
    write(out)
  }

  func write(_ out: [String: Any]) {
    if let d = try? JSONSerialization.data(withJSONObject: out, options: [.sortedKeys]) {
      try? d.write(to: URL(fileURLWithPath: job.out))
    }
  }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
guard CommandLine.arguments.count == 2, let data = CommandLine.arguments[1].data(using: .utf8),
  let job = try? JSONDecoder().decode(Job.self, from: data)
else {
  FileHandle.standardError.write("usage: mb-wkprobe JOB_JSON\n".data(using: .utf8)!)
  exit(2)
}
if job.lifeline == true { watchLifeline() }
Task { @MainActor in
  let probe = Probe(job: job)
  await probe.run()
  if let delay = job.exitDelayMs, delay > 0 { await probe.sleepMs(delay) }
  ProcessInfo.processInfo.endActivity(napGuard)
  exit(0)
}
app.run()
