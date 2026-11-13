import CoreGraphics
import Foundation
import Testing
@testable import ShellCore

@Suite struct AppIconMarkTests {
    /// The icon masters in `AppIcon/`, beside this package's tests.
    private func master(_ name: String) throws -> String {
        let package = URL(filePath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent()
        return try String(contentsOf: package.appending(path: "AppIcon/\(name)"), encoding: .utf8)
    }

    @Test func theMarkIsTheGlyphGroupOfBothMasters() throws {
        // A master regenerated without AppIconMarkGeometry.swift, or the reverse, fails here.
        for name in ["metabrowser-icon.svg", "metabrowser-icon-dev.svg"] {
            let svg = try master(name)
            for glyph in AppIconMark.glyphs {
                #expect(svg.contains(#"<path d="\#(glyph.path)" fill="\#(glyph.fill)"/>"#), "\(name)")
            }
        }
        #expect(AppIconMark.glyphs.map(\.fill) == ["#ECC44B", "#C896FF"])
    }

    @Test func theOutlinesSpanTheInkTheGeneratorMeasured() throws {
        let paths = AppIconMark.glyphs.compactMap { AppIconMark.path($0.path) }
        #expect(paths.count == 2)
        let bounds = paths.map(\.boundingBoxOfPath).reduce(CGRect.null) { $0.union($1) }
        let ink = AppIconMark.ink
        for (measured, expected) in [
            (bounds.minX, ink.minX), (bounds.maxX, ink.maxX), (bounds.minY, ink.minY), (bounds.maxY, ink.maxY),
        ] {
            #expect(abs(measured - expected) < 0.001)
        }
        // Cap line to baseline, as the README's parameters give them.
        #expect(abs(ink.minY - 172.023) < 0.001 && abs(ink.maxY - 339) < 0.001)
    }

    @Test func pathDataOutsideTheGeneratorsSubsetIsRefused() {
        #expect(AppIconMark.path("M0 0L10 0Q10 10 0 10C0 5 0 5 0 0Z") != nil)
        #expect(AppIconMark.path("") == nil)
        #expect(AppIconMark.path("m0 0l10 0z") == nil)  // relative commands
        #expect(AppIconMark.path("M0 0L10") == nil)  // a coordinate short
        #expect(AppIconMark.path("M0 0A5 5 0 0 1 10 0") == nil)  // an arc
        #expect(AppIconMark.path("M0 zero") == nil)
    }

    @Test func everyFillReadsOnItsTitleBar() {
        let light = AppIconMark.titleBarFills(dark: false), dark = AppIconMark.titleBarFills(dark: true)
        // The dark title bar shows the icon's own fills.
        #expect(dark == AppIconMark.glyphs.map(\.fill))
        for fill in dark { #expect(contrast(fill, "#1E1E1E") >= 3) }
        // The light one needs its own: the icon's fall short there.
        for fill in AppIconMark.glyphs.map(\.fill) { #expect(contrast(fill, "#FFFFFF") < 3) }
        // 4:1, past the 3:1 graphics need, since the user asked for darker fills there.
        for fill in light { #expect(contrast(fill, "#FFFFFF") >= 4) }
    }

    @Test func theLightTitleBarsFillsKeepTheIconsHues() {
        for (tint, fill) in zip(AppIconMark.titleBarFills(dark: false), AppIconMark.glyphs.map(\.fill)) {
            let difference = abs(hue(tint) - hue(fill))
            #expect(min(difference, 360 - difference) < 1, "\(tint) against \(fill)")
            #expect(lightness(tint) < lightness(fill))
        }
    }

    // MARK: - Color arithmetic

    private func linear(_ hex: String) -> [Double] {
        let rgb = AppIconMark.rgb(hex)!
        return [rgb.red, rgb.green, rgb.blue].map { c in
            let v = Double(c)
            return v <= 0.04045 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4)
        }
    }

    /// WCAG 2 contrast ratio.
    private func contrast(_ a: String, _ b: String) -> Double {
        func luminance(_ hex: String) -> Double {
            let c = linear(hex)
            return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
        }
        let x = luminance(a), y = luminance(b)
        return (max(x, y) + 0.05) / (min(x, y) + 0.05)
    }

    /// OKLab's L, a, and b.
    private func oklab(_ hex: String) -> (l: Double, a: Double, b: Double) {
        let c = linear(hex)
        let l = cbrt(0.4122214708 * c[0] + 0.5363325363 * c[1] + 0.0514459929 * c[2])
        let m = cbrt(0.2119034982 * c[0] + 0.6806995451 * c[1] + 0.1073969566 * c[2])
        let s = cbrt(0.0883024619 * c[0] + 0.2817188376 * c[1] + 0.6299787005 * c[2])
        return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)
    }

    private func hue(_ hex: String) -> Double {
        let lab = oklab(hex)
        let degrees = atan2(lab.b, lab.a) * 180 / .pi
        return degrees < 0 ? degrees + 360 : degrees
    }

    private func lightness(_ hex: String) -> Double { oklab(hex).l }
}
