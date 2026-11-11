// Composes review sheets from PNGs and captions, for scripts/build-icon.sh --review.
// Usage: review-sheet SPEC OUT.png, where SPEC has one command per line (top-left origin):
//   canvas W H #RRGGBB
//   rect X Y W H #RRGGBB
//   image PATH X Y [W H [nearest]]
//   text X Y SIZE #RRGGBB [bold] CAPTION...
import AppKit
import CoreText
import Foundation
import ImageIO

func color(_ hex: String) -> CGColor {
    let n = UInt32(hex.dropFirst(), radix: 16) ?? 0
    return CGColor(srgbRed: CGFloat((n >> 16) & 255) / 255, green: CGFloat((n >> 8) & 255) / 255,
                   blue: CGFloat(n & 255) / 255, alpha: 1)
}

let arguments = CommandLine.arguments
guard arguments.count == 3 else {
    FileHandle.standardError.write(Data("usage: review-sheet SPEC OUT.png\n".utf8))
    exit(2)
}
let lines = try String(contentsOfFile: arguments[1], encoding: .utf8).split(separator: "\n").map(String.init)
var context: CGContext?
var height = 0
for line in lines where !line.trimmingCharacters(in: .whitespaces).isEmpty {
    let parts = line.split(separator: " ", omittingEmptySubsequences: true).map(String.init)
    func n(_ i: Int) -> CGFloat { CGFloat(Double(parts[i]) ?? 0) }
    switch parts[0] {
    case "canvas":
        let w = Int(parts[1])!, h = Int(parts[2])!
        height = h
        context = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                            space: CGColorSpace(name: CGColorSpace.sRGB)!,
                            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)
        context!.setFillColor(color(parts[3]))
        context!.fill(CGRect(x: 0, y: 0, width: w, height: h))
    case "rect":
        context!.setFillColor(color(parts[5]))
        context!.fill(CGRect(x: n(1), y: CGFloat(height) - n(2) - n(4), width: n(3), height: n(4)))
    case "image":
        let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: parts[1]) as CFURL, nil)!
        let image = CGImageSourceCreateImageAtIndex(source, 0, nil)!
        let w = parts.count > 5 ? n(4) : CGFloat(image.width), h = parts.count > 5 ? n(5) : CGFloat(image.height)
        context!.interpolationQuality = parts.count > 6 && parts[6] == "nearest" ? .none : .high
        context!.draw(image, in: CGRect(x: n(2), y: CGFloat(height) - n(3) - h, width: w, height: h))
    case "text":
        let bold = parts[5] == "bold"
        let caption = parts[(bold ? 6 : 5)...].joined(separator: " ")
        let font = NSFont.systemFont(ofSize: n(3), weight: bold ? .semibold : .regular)
        let attributed = NSAttributedString(string: caption, attributes: [
            .font: font, .foregroundColor: NSColor(cgColor: color(parts[4]))!,
        ])
        let ctLine = CTLineCreateWithAttributedString(attributed)
        context!.textPosition = CGPoint(x: n(1), y: CGFloat(height) - n(2) - font.ascender)
        CTLineDraw(ctLine, context!)
    default:
        FileHandle.standardError.write(Data("review-sheet: unknown command \(parts[0])\n".utf8))
        exit(1)
    }
}
let rep = NSBitmapImageRep(cgImage: context!.makeImage()!)
try rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: arguments[2]))
