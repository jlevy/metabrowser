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
        // child environment, logs, recent folders, and the navigation policy.
        .target(name: "ShellCore", swiftSettings: settings),
        // The AppKit app: lifecycle, menus, windows, and WKWebView.
        .executableTarget(
            name: "Metabrowser", dependencies: ["ShellCore"], swiftSettings: settings),
        .testTarget(
            name: "ShellCoreTests", dependencies: ["ShellCore"], swiftSettings: settings),
    ],
    swiftLanguageModes: [.v6]
)
