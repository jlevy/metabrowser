// swift-tools-version: 6.3
// The native macOS app for Metabrowser. See README.md.
import PackageDescription

// Swift 6 language mode with main-actor default isolation (SE-0466): AppKit code is
// main-actor by nature, and the few types that cross threads say `nonisolated`.
let settings: [SwiftSetting] = [.defaultIsolation(MainActor.self)]

let package = Package(
    name: "Metabrowser",
    platforms: [.macOS(.v26)],
    products: [
        .executable(name: "Metabrowser", targets: ["Metabrowser"])
    ],
    targets: [
        // Everything testable without a window: supervision, runtime discovery, the
        // child environment, logs, files opened in folders, tabs, the saved session, and
        // the navigation policy.
        .target(name: "ShellCore", swiftSettings: settings),
        // The web view class a window holds and its container: a library of their own, so
        // the WebKit measurement gate builds the same views as the app.
        .target(name: "ShellViews", dependencies: ["ShellCore"], swiftSettings: settings),
        // The AppKit app: lifecycle, menus, windows, and WKWebView.
        .executableTarget(
            name: "Metabrowser", dependencies: ["ShellCore", "ShellViews"], swiftSettings: settings),
        // The WebKit measurement gate's window (webkit-gate/run.mjs). A developer tool that
        // no product ships; `make test` builds it, so a change to what it shares with the
        // app cannot break it unnoticed.
        .executableTarget(
            name: "WebKitDriver", dependencies: ["ShellCore", "ShellViews"],
            path: "webkit-gate/driver", swiftSettings: settings),
        .testTarget(
            name: "ShellCoreTests", dependencies: ["ShellCore"], swiftSettings: settings),
    ],
    swiftLanguageModes: [.v6]
)
