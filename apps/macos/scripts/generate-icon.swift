// Draws the app icon into an .iconset folder for iconutil, so the source of truth is
// this file rather than a binary. Usage: swift scripts/generate-icon.swift OUT.iconset
import AppKit

guard CommandLine.arguments.count == 2 else {
    FileHandle.standardError.write(Data("usage: generate-icon.swift OUT.iconset\n".utf8))
    exit(2)
}
let destination = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)

func draw(pixels: Int) -> NSBitmapImageRep {
    let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels, bitsPerSample: 8,
        samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
        bytesPerRow: 0, bitsPerPixel: 0)!
    let size = CGFloat(pixels)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
    // The macOS icon grid: an 824-point rounded square centered in 1024.
    let inset = size * 100 / 1024
    let tile = NSRect(x: inset, y: inset, width: size - 2 * inset, height: size - 2 * inset)
    let shape = NSBezierPath(roundedRect: tile, xRadius: tile.width * 0.225, yRadius: tile.width * 0.225)
    NSGradient(
        starting: NSColor(srgbRed: 0.16, green: 0.42, blue: 0.86, alpha: 1),
        ending: NSColor(srgbRed: 0.07, green: 0.20, blue: 0.48, alpha: 1))!
        .draw(in: shape, angle: -90)
    let configuration = NSImage.SymbolConfiguration(pointSize: tile.width * 0.5, weight: .semibold)
        .applying(NSImage.SymbolConfiguration(paletteColors: [.white]))
    if let symbol = NSImage(systemSymbolName: "folder.fill", accessibilityDescription: nil)?
        .withSymbolConfiguration(configuration)
    {
        let glyph = symbol.size
        let scale = min(tile.width * 0.62 / glyph.width, tile.height * 0.62 / glyph.height)
        let drawn = NSSize(width: glyph.width * scale, height: glyph.height * scale)
        symbol.draw(in: NSRect(
            x: tile.midX - drawn.width / 2, y: tile.midY - drawn.height / 2,
            width: drawn.width, height: drawn.height))
    }
    NSGraphicsContext.restoreGraphicsState()
    return bitmap
}

for points in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let suffix = scale == 2 ? "@2x" : ""
        let file = destination.appendingPathComponent("icon_\(points)x\(points)\(suffix).png")
        try draw(pixels: points * scale).representation(using: .png, properties: [:])!.write(to: file)
    }
}
