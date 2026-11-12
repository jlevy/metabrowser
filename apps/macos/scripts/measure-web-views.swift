// Measures what a folder tab's web view costs in WebKit and what discarding it returns:
// the basis of TabDiscardPolicy.defaultLiveBackgroundTabs. Start a server, then:
//
//   metab FOLDER --no-open --port 8650
//   swift apps/macos/scripts/measure-web-views.swift http://127.0.0.1:8650/view/ [views]
//
// It loads the page in several web views, each in its own window, and reports each
// one's WebContent process and footprint (`proc_pid_rusage`), whether that process
// ends once its view is released, whether a never-loaded view has a process at all,
// and how long a fresh view takes to load the page from the same, warm server: what a
// discarded tab costs when it is shown again. The process id comes from WebKit's
// `_webProcessIdentifier`, a private property read only here, never by the app.
import AppKit
import Darwin
import WebKit

/// Time for the page's own fetches and rendering after `didFinish`, before measuring.
let settle = Duration.seconds(8)
/// Checks of a released view's process, after this long each.
let releaseChecks: [Duration] = [.seconds(1), .seconds(3), .seconds(10)]
/// Loads of a fresh view against the warm server.
let reloadCount = 5
/// Pause between reloads, so each fresh view's process ends before the next starts.
let reloadPause = Duration.seconds(2)
let defaultViews = 4

@MainActor final class Loader: NSObject, WKNavigationDelegate {
    private var waiting: CheckedContinuation<Void, Never>?

    func load(_ url: URL, in view: WKWebView) async -> Duration {
        let start = ContinuousClock.now
        await withCheckedContinuation { continuation in
            waiting = continuation
            view.navigationDelegate = self
            view.load(URLRequest(url: url))
        }
        return start.duration(to: .now)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { finish() }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: any Error) {
        print("load failed: \(error.localizedDescription)")
        finish()
    }

    func webView(
        _ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: any Error
    ) {
        print("load failed: \(error.localizedDescription)")
        finish()
    }

    private func finish() {
        waiting?.resume()
        waiting = nil
    }
}

@MainActor func webProcess(of view: WKWebView) -> pid_t {
    (view.value(forKey: "_webProcessIdentifier") as? NSNumber)?.int32Value ?? 0
}

func footprint(of pid: pid_t) -> String {
    var info = rusage_info_v4()
    let result = withUnsafeMutablePointer(to: &info) { pointer in
        pointer.withMemoryRebound(to: rusage_info_t?.self, capacity: 1) { proc_pid_rusage(pid, RUSAGE_INFO_V4, $0) }
    }
    return result == 0 ? String(format: "%.0f MB", Double(info.ri_phys_footprint) / 1_048_576) : "gone"
}

func milliseconds(_ duration: Duration) -> Int {
    Int(duration.components.seconds * 1000 + duration.components.attoseconds / 1_000_000_000_000_000)
}

@MainActor func window(showing view: WKWebView) -> NSWindow {
    let window = NSWindow(
        contentRect: NSRect(x: 0, y: 0, width: 1200, height: 820), styleMask: [.titled, .resizable],
        backing: .buffered, defer: false)
    window.isReleasedWhenClosed = false
    window.contentView = view
    window.orderFront(nil)
    return window
}

@MainActor func release(_ view: WKWebView, _ window: NSWindow) {
    view.navigationDelegate = nil
    window.contentView = nil
    window.close()
}

@MainActor func measure(_ url: URL, views count: Int) async {
    let loader = Loader()
    let neverLoaded = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
    let neverLoadedWindow = window(showing: neverLoaded)
    try? await Task.sleep(for: .seconds(1))
    print("a never-loaded view's web process: \(webProcess(of: neverLoaded)) (0 is none)")
    release(neverLoaded, neverLoadedWindow)

    var tabs: [(view: WKWebView, window: NSWindow)] = []
    for index in 0..<count {
        let view = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        let shown = window(showing: view)
        print("view \(index): first load \(milliseconds(await loader.load(url, in: view))) ms")
        tabs.append((view, shown))
    }
    try? await Task.sleep(for: settle)
    let processes = tabs.map { webProcess(of: $0.view) }
    for (index, pid) in processes.enumerated() {
        print("view \(index): web process \(pid), footprint \(footprint(of: pid))")
    }
    print("distinct web processes for \(count) views: \(Set(processes).count)")

    let released = tabs.removeFirst()
    release(released.view, released.window)
    var waited = Duration.zero
    for check in releaseChecks {
        try? await Task.sleep(for: check - waited)
        waited = check
        print("\(milliseconds(check)) ms after releasing view 0: web process \(processes[0]) \(footprint(of: processes[0]))")
    }

    var reloads: [Int] = []
    for _ in 0..<reloadCount {
        let view = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        let shown = window(showing: view)
        reloads.append(milliseconds(await loader.load(url, in: view)))
        release(view, shown)
        try? await Task.sleep(for: reloadPause)
    }
    print("a fresh view loading from the warm server, ms to didFinish: \(reloads)")
    tabs.forEach { release($0.view, $0.window) }
}

guard CommandLine.arguments.count > 1, let url = URL(string: CommandLine.arguments[1]) else {
    print("usage: swift measure-web-views.swift URL [views]")
    exit(2)
}
let count = CommandLine.arguments.count > 2 ? Int(CommandLine.arguments[2]) ?? defaultViews : defaultViews
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
Task { @MainActor in
    await measure(url, views: count)
    exit(0)
}
app.run()
