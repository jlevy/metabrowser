// Renders the icon's SVG masters to PNG, deterministically and with no
// color management: every value is an sRGB number composited in sRGB, as Figma does.
//
// It implements exactly the SVG subset Figma's SVG export of the icon uses, and it stops
// with an error on any element, attribute, or value outside that subset, so an edited
// master cannot render silently wrong. The subset: <svg> with a viewBox; <g>, <path>,
// <rect>, and <use>; presentation attributes (no style sheets); luminance <mask> in user
// space; <linearGradient> in user space; and <filter> chains of feFlood, feColorMatrix
// (matrix), feMorphology, feOffset, feGaussianBlur, feComposite, and feBlend (normal).
//
// Why not WebKit or NSImage: NSImage (CoreSVG) drops the filters, which carry the panel's
// drop shadow and the letters' inner shadow, and a WebKit snapshot passes through the
// display's color profile (the sister app's #1F2020 panel came back as #1C2222), so its output
// depends on the Mac that runs it.
//
// Usage: render-svg [--time-limit SECONDS] [--internal PIXELS] MASTER.svg OUT.png PIXELS [OUT.png PIXELS ...]
// Each PIXELS must divide the internal render size (2048 by default). With --time-limit, the
// kernel ends the renderer with SIGALRM once SECONDS pass, so a file that sends it into a
// loop cannot hang its caller, and no watchdog process is needed to stop it.
import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

struct RenderError: Error, CustomStringConvertible {
    let description: String
    init(_ message: String) { description = message }
}

// MARK: - Pixels

/// Premultiplied RGBA in [0, 1], row 0 at the top.
struct Layer {
    let width: Int, height: Int
    var data: [Float]
    init(_ width: Int, _ height: Int) {
        self.width = width
        self.height = height
        data = [Float](repeating: 0, count: width * height * 4)
    }
    var count: Int { width * height }
}

/// Antialiased coverage of a filled path: exact horizontally, and sampled on 16 sub-scanlines
/// per row with the fill rule applied on each, so overlapping contours (the font's B overlaps
/// its stem and bowls) never count twice.
///
/// CoreGraphics only builds the paths (and stroke outlines); this rasterizes them, so the
/// output depends on this file and not on the system's antialiasing, which Apple does not
/// specify and may change between releases.
func coverage(of path: CGPath, transform: CGAffineTransform, width: Int, height: Int, evenOdd: Bool) -> [Float] {
    // Flatten to edges in pixel space.
    struct Edge { var x0, y0, x1, y1: Double; var winding: Int }
    var edges: [Edge] = []
    var start = CGPoint.zero, current = CGPoint.zero
    func line(to p: CGPoint) {
        if p.y != current.y {
            edges.append(current.y < p.y
                ? Edge(x0: current.x, y0: current.y, x1: p.x, y1: p.y, winding: 1)
                : Edge(x0: p.x, y0: p.y, x1: current.x, y1: current.y, winding: -1))
        }
        current = p
    }
    func flatten(_ points: [CGPoint], depth: Int = 0) {
        // De Casteljau subdivision until the control points lie within 0.01 px of the chord.
        let a = points.first!, b = points.last!
        let dx = b.x - a.x, dy = b.y - a.y
        let length = max((dx * dx + dy * dy).squareRoot(), 1e-9)
        let flat = points.dropFirst().dropLast().allSatisfy { abs(($0.x - a.x) * dy - ($0.y - a.y) * dx) / length < 0.01 }
        if flat || depth > 18 { line(to: b); return }
        var left = [a], right = [b], level = points
        while level.count > 1 {
            level = zip(level, level.dropFirst()).map { CGPoint(x: ($0.x + $1.x) / 2, y: ($0.y + $1.y) / 2) }
            left.append(level.first!)
            right.insert(level.last!, at: 0)
        }
        flatten(left, depth: depth + 1)
        flatten(right, depth: depth + 1)
    }
    path.applyWithBlock { element in
        let e = element.pointee
        func p(_ i: Int) -> CGPoint { e.points[i].applying(transform) }
        switch e.type {
        case .moveToPoint:
            if current != start { line(to: start) }
            start = p(0); current = start
        case .addLineToPoint: line(to: p(0))
        case .addQuadCurveToPoint: flatten([current, p(0), p(1)])
        case .addCurveToPoint: flatten([current, p(0), p(1), p(2)])
        case .closeSubpath: line(to: start)
        @unknown default: break
        }
    }
    if current != start { line(to: start) }

    let samples = 16
    var result = [Float](repeating: 0, count: width * height)
    var direct = [Double](repeating: 0, count: width + 2)
    var steps = [Double](repeating: 0, count: width + 2)
    edges.sort { $0.y0 < $1.y0 }
    var next = 0
    var active: [Edge] = []
    var crossings: [(x: Double, winding: Int)] = []
    let weight = 1.0 / Double(samples)
    for row in 0..<height {
        for i in 0..<direct.count { direct[i] = 0; steps[i] = 0 }
        for sub in 0..<samples {
            let y = Double(row) + (Double(sub) + 0.5) / Double(samples)
            while next < edges.count && edges[next].y0 <= y { active.append(edges[next]); next += 1 }
            active.removeAll { $0.y1 <= y }
            crossings.removeAll(keepingCapacity: true)
            for e in active where e.y0 <= y {
                crossings.append((e.x0 + (y - e.y0) * (e.x1 - e.x0) / (e.y1 - e.y0), e.winding))
            }
            crossings.sort { $0.x < $1.x }
            var winding = 0
            for (index, crossing) in crossings.enumerated() {
                winding += crossing.winding
                let inside = evenOdd ? winding % 2 != 0 : winding != 0
                guard inside, index + 1 < crossings.count else { continue }
                // The span [a, b] is inside: exact partial pixels at its ends, whole pixels between.
                let a = min(max(crossing.x, 0), Double(width)), b = min(max(crossings[index + 1].x, 0), Double(width))
                if b <= a { continue }
                let ia = Int(a), ib = Int(b)
                if ia == ib {
                    direct[ia] += (b - a) * weight
                } else {
                    direct[ia] += (Double(ia + 1) - a) * weight
                    direct[ib] += (b - Double(ib)) * weight
                    steps[ia + 1] += weight
                    steps[ib] -= weight
                }
            }
        }
        var run = 0.0
        for x in 0..<width {
            run += steps[x]
            result[row * width + x] = Float(min(1, max(0, run + direct[x])))
        }
    }
    return result
}

/// Separable Gaussian blur of one channel, with transparent edges.
func gaussian(_ source: [Float], width: Int, height: Int, sigmaX: Double, sigmaY: Double) -> [Float] {
    func kernel(_ sigma: Double) -> [Float] {
        let radius = Int(ceil(sigma * 3))
        let values = (-radius...radius).map { exp(-Double($0 * $0) / (2 * sigma * sigma)) }
        let sum = values.reduce(0, +)
        return values.map { Float($0 / sum) }
    }
    var result = source
    if sigmaX > 0.05 {
        let k = kernel(sigmaX), r = k.count / 2
        var out = [Float](repeating: 0, count: source.count)
        for y in 0..<height {
            let row = y * width
            for x in 0..<width {
                var sum: Float = 0
                for j in max(-r, -x)...min(r, width - 1 - x) { sum += k[j + r] * result[row + x + j] }
                out[row + x] = sum
            }
        }
        result = out
    }
    if sigmaY > 0.05 {
        let k = kernel(sigmaY), r = k.count / 2
        var out = [Float](repeating: 0, count: source.count)
        for y in 0..<height {
            for x in 0..<width {
                var sum: Float = 0
                for j in max(-r, -y)...min(r, height - 1 - y) { sum += k[j + r] * result[(y + j) * width + x] }
                out[y * width + x] = sum
            }
        }
        result = out
    }
    return result
}

// MARK: - Paint

struct RGBA { var r, g, b, a: Float }

enum Paint {
    case none
    case color(RGBA)
    case reference(String)
}

func parseColor(_ text: String) throws -> RGBA {
    let value = text.trimmingCharacters(in: .whitespaces).lowercased()
    switch value {
    case "black": return RGBA(r: 0, g: 0, b: 0, a: 1)
    case "white": return RGBA(r: 1, g: 1, b: 1, a: 1)
    default: break
    }
    guard value.hasPrefix("#") else { throw RenderError("unsupported color \(text)") }
    var hex = String(value.dropFirst())
    if hex.count == 3 { hex = hex.map { "\($0)\($0)" }.joined() }
    guard hex.count == 6, let n = UInt32(hex, radix: 16) else { throw RenderError("unsupported color \(text)") }
    return RGBA(r: Float((n >> 16) & 255) / 255, g: Float((n >> 8) & 255) / 255, b: Float(n & 255) / 255, a: 1)
}

func parsePaint(_ text: String) throws -> Paint {
    let value = text.trimmingCharacters(in: .whitespaces)
    if value == "none" { return .none }
    if value.hasPrefix("url(#") && value.hasSuffix(")") {
        return .reference(String(value.dropFirst(5).dropLast()))
    }
    return .color(try parseColor(value))
}

// MARK: - Path data

func parsePath(_ d: String) throws -> CGPath {
    var tokens: [String] = []
    var current = ""
    func flush() { if !current.isEmpty { tokens.append(current); current = "" } }
    var previous: Character = " "
    for ch in d {
        if ch.isLetter && ch != "e" && ch != "E" {
            flush(); tokens.append(String(ch))
        } else if ch == "," || ch.isWhitespace {
            flush()
        } else if ch == "-" && previous != "e" && previous != "E" {
            flush(); current.append(ch)
        } else if ch == "." && current.contains(".") {
            flush(); current.append(ch)
        } else {
            current.append(ch)
        }
        previous = ch
    }
    flush()

    let path = CGMutablePath()
    var index = 0
    // The command a run of numbers repeats. Nil at the start and after a close-path, which
    // takes no numbers, so a stray number there is an error rather than a loop.
    var command: Character?
    var point = CGPoint.zero
    var start = CGPoint.zero
    func number() throws -> CGFloat {
        guard index < tokens.count, let v = Double(tokens[index]) else { throw RenderError("bad path data near token \(index)") }
        index += 1
        return CGFloat(v)
    }
    while index < tokens.count {
        let before = index
        if let c = tokens[index].first, tokens[index].count == 1, c.isLetter {
            command = c
            index += 1
        }
        guard let current = command else { throw RenderError("path data has a number with no command at token \(index)") }
        var next: Character? = current  // numbers that follow repeat it
        let relative = current.isLowercase
        let base = relative ? point : .zero
        switch current.uppercased().first! {
        case "M":
            point = CGPoint(x: base.x + (try number()), y: base.y + (try number()))
            path.move(to: point)
            start = point
            next = relative ? "l" : "L"
        case "L":
            point = CGPoint(x: base.x + (try number()), y: base.y + (try number()))
            path.addLine(to: point)
        case "H":
            point.x = (relative ? point.x : 0) + (try number())
            path.addLine(to: point)
        case "V":
            point.y = (relative ? point.y : 0) + (try number())
            path.addLine(to: point)
        case "C":
            let c1 = CGPoint(x: base.x + (try number()), y: base.y + (try number()))
            let c2 = CGPoint(x: base.x + (try number()), y: base.y + (try number()))
            point = CGPoint(x: base.x + (try number()), y: base.y + (try number()))
            path.addCurve(to: point, control1: c1, control2: c2)
        case "Q":
            let c = CGPoint(x: base.x + (try number()), y: base.y + (try number()))
            point = CGPoint(x: base.x + (try number()), y: base.y + (try number()))
            path.addQuadCurve(to: point, control: c)
        case "Z":
            path.closeSubpath()
            point = start
            next = nil
        default:
            throw RenderError("unsupported path command \(current)")
        }
        // Every pass consumes a token, so malformed data ends in an error, never a hang.
        guard index > before else { throw RenderError("path data does not advance at token \(index)") }
        command = next
    }
    return path
}

// MARK: - Document

final class Document {
    let root: XMLElement
    var byID: [String: XMLElement] = [:]
    let viewBox: CGRect

    init(url: URL) throws {
        let xml = try XMLDocument(contentsOf: url, options: [])
        guard let root = xml.rootElement(), root.name == "svg" else { throw RenderError("not an SVG document") }
        self.root = root
        let box = (root.attribute(forName: "viewBox")?.stringValue ?? "")
            .split(whereSeparator: { $0 == " " || $0 == "," }).compactMap { Double($0) }
        guard box.count == 4 else { throw RenderError("the root <svg> needs a viewBox") }
        viewBox = CGRect(x: box[0], y: box[1], width: box[2], height: box[3])
        func index(_ element: XMLElement) {
            if let id = element.attribute(forName: "id")?.stringValue { byID[id] = element }
            for child in element.children ?? [] { if let e = child as? XMLElement { index(e) } }
        }
        index(root)
    }

    func element(_ id: String) throws -> XMLElement {
        guard let e = byID[id] else { throw RenderError("missing #\(id)") }
        return e
    }
}

func attribute(_ element: XMLElement, _ name: String) -> String? {
    element.attribute(forName: name)?.stringValue
}

func number(_ element: XMLElement, _ name: String, _ fallback: Double? = nil) throws -> Double {
    if let text = attribute(element, name) {
        guard let v = Double(text) else { throw RenderError("<\(element.name ?? "")> \(name)=\(text) is not a number") }
        return v
    }
    if let fallback { return fallback }
    throw RenderError("<\(element.name ?? "")> needs \(name)")
}

/// Inherited presentation attributes.
struct Style {
    var fill: Paint = .color(RGBA(r: 0, g: 0, b: 0, a: 1))
    var fillRuleEvenOdd = false
    var stroke: Paint = .none
    var strokeWidth: Double = 1
}

// Attributes the renderer understands, per element; anything else is an error.
let presentation: Set<String> = ["fill", "fill-rule", "clip-rule", "stroke", "stroke-width"]
let allowed: [String: Set<String>] = [
    "svg": ["width", "height", "viewBox", "fill", "xmlns", "xmlns:xlink"],
    "g": ["filter", "mask", "opacity"],
    "path": ["d", "id", "mask", "filter", "opacity"],
    "rect": ["x", "y", "width", "height", "id"],
    "use": ["xlink:href", "href"],
    "defs": [],
    "mask": ["id", "maskUnits", "x", "y", "width", "height"],
]

// What each filter primitive may carry: the attributes the renderer reads. A primitive
// subregion (x, y, width, height) or any presentation attribute would be ignored, so it
// is an error.
let primitiveAttributes: [String: Set<String>] = [
    "feFlood": ["flood-color", "flood-opacity", "result"],
    "feColorMatrix": ["in", "type", "values", "result"],
    "feMorphology": ["in", "radius", "operator", "result"],
    "feOffset": ["in", "dx", "dy", "result"],
    "feGaussianBlur": ["in", "stdDeviation", "result"],
    "feComposite": ["in", "in2", "operator", "k1", "k2", "k3", "k4", "result"],
    "feBlend": ["in", "in2", "mode", "result"],
]

/// Rejects any attribute of `element` outside `names`.
func requireOnly(_ names: Set<String>, on element: XMLElement) throws {
    for a in element.attributes ?? [] where !names.contains(a.name ?? "") {
        throw RenderError("unsupported attribute \(a.name ?? "") on <\(element.name ?? "")>")
    }
}

// MARK: - Renderer

final class Renderer {
    let document: Document
    let width: Int, height: Int
    let scale: CGFloat
    let ctm: CGAffineTransform

    init(document: Document, pixels: Int) {
        self.document = document
        width = pixels
        height = pixels
        scale = CGFloat(pixels) / document.viewBox.width
        ctm = CGAffineTransform(translationX: -document.viewBox.minX, y: -document.viewBox.minY)
            .concatenating(CGAffineTransform(scaleX: scale, y: scale))
    }

    func render() throws -> Layer {
        var layer = Layer(width, height)
        var style = Style()
        try check(document.root)
        try applyPresentation(document.root, to: &style)
        for child in document.root.children ?? [] {
            if let e = child as? XMLElement { try draw(e, style: style, into: &layer) }
        }
        return layer
    }

    func applyPresentation(_ element: XMLElement, to style: inout Style) throws {
        if let v = attribute(element, "fill") { style.fill = try parsePaint(v) }
        if let v = attribute(element, "fill-rule") {
            guard v == "evenodd" || v == "nonzero" else { throw RenderError("fill-rule \(v)") }
            style.fillRuleEvenOdd = v == "evenodd"
        }
        if let v = attribute(element, "stroke") { style.stroke = try parsePaint(v) }
        if attribute(element, "stroke-width") != nil { style.strokeWidth = try number(element, "stroke-width") }
    }

    /// Rejects attributes outside the subset.
    func check(_ element: XMLElement) throws {
        let name = element.name ?? ""
        guard let names = allowed[name] else { return }
        for a in element.attributes ?? [] {
            let key = a.name ?? ""
            if !names.contains(key) && !presentation.contains(key) {
                throw RenderError("unsupported attribute \(key) on <\(name)>")
            }
        }
    }

    func draw(_ element: XMLElement, style inherited: Style, into target: inout Layer) throws {
        let name = element.name ?? ""
        switch name {
        case "defs", "mask", "filter", "linearGradient": return
        case "g", "path", "rect", "use": break
        default: throw RenderError("unsupported element <\(name)>")
        }
        try check(element)
        var style = inherited
        try applyPresentation(element, to: &style)

        let filter = attribute(element, "filter")
        let mask = attribute(element, "mask")
        let opacity = try number(element, "opacity", 1)
        if filter == nil && mask == nil && opacity == 1 {
            try drawContent(element, style: style, into: &target)
            return
        }
        var layer = Layer(width, height)
        try drawContent(element, style: style, into: &layer)
        if let filter { layer = try applyFilter(try reference(filter), source: layer) }
        if let mask { try applyMask(try reference(mask), to: &layer) }
        for i in 0..<layer.count * 4 { layer.data[i] *= Float(opacity) }
        over(layer, onto: &target)
    }

    func reference(_ value: String) throws -> XMLElement {
        guard value.hasPrefix("url(#"), value.hasSuffix(")") else { throw RenderError("bad reference \(value)") }
        return try document.element(String(value.dropFirst(5).dropLast()))
    }

    func drawContent(_ element: XMLElement, style: Style, into target: inout Layer) throws {
        switch element.name ?? "" {
        case "g":
            for child in element.children ?? [] {
                if let e = child as? XMLElement { try draw(e, style: style, into: &target) }
            }
        case "use":
            guard let href = attribute(element, "xlink:href") ?? attribute(element, "href"), href.hasPrefix("#") else {
                throw RenderError("<use> needs an #id reference")
            }
            let referenced = try document.element(String(href.dropFirst()))
            try draw(referenced, style: style, into: &target)
        case "path":
            try paintShape(try parsePath(attribute(element, "d") ?? ""), style: style, into: &target)
        case "rect":
            let rect = CGRect(x: try number(element, "x", 0), y: try number(element, "y", 0),
                              width: try number(element, "width"), height: try number(element, "height"))
            try paintShape(CGPath(rect: rect, transform: nil), style: style, into: &target)
        default:
            throw RenderError("cannot draw <\(element.name ?? "")>")
        }
    }

    func paintShape(_ path: CGPath, style: Style, into target: inout Layer) throws {
        if case .none = style.fill {} else {
            let cov = coverage(of: path, transform: ctm, width: width, height: height, evenOdd: style.fillRuleEvenOdd)
            try fill(cov, with: style.fill, into: &target)
        }
        if case .none = style.stroke {} else {
            // SVG's defaults: butt caps, miter joins, miter limit 4. The outline fills nonzero.
            let outline = path.copy(strokingWithWidth: CGFloat(style.strokeWidth), lineCap: .butt,
                                    lineJoin: .miter, miterLimit: 4)
            let cov = coverage(of: outline, transform: ctm, width: width, height: height, evenOdd: false)
            try fill(cov, with: style.stroke, into: &target)
        }
    }

    /// The paint's color at a pixel center.
    func shader(_ paint: Paint) throws -> (Int, Int) -> RGBA {
        switch paint {
        case .none: return { _, _ in RGBA(r: 0, g: 0, b: 0, a: 0) }
        case .color(let c): return { _, _ in c }
        case .reference(let id):
            let gradient = try document.element(id)
            guard gradient.name == "linearGradient" else { throw RenderError("unsupported paint server <\(gradient.name ?? "")>") }
            for a in gradient.attributes ?? [] {
                guard ["id", "x1", "y1", "x2", "y2", "gradientUnits"].contains(a.name ?? "") else {
                    throw RenderError("unsupported attribute \(a.name ?? "") on <linearGradient>")
                }
            }
            guard attribute(gradient, "gradientUnits") == "userSpaceOnUse" else {
                throw RenderError("linearGradient #\(id) must use gradientUnits=userSpaceOnUse")
            }
            let p1 = CGPoint(x: try number(gradient, "x1"), y: try number(gradient, "y1"))
            let p2 = CGPoint(x: try number(gradient, "x2"), y: try number(gradient, "y2"))
            var stops: [(Float, RGBA)] = []
            for child in gradient.children ?? [] {
                guard let stop = child as? XMLElement, stop.name == "stop" else { continue }
                try requireOnly(["offset", "stop-color", "stop-opacity"], on: stop)
                var color = try parseColor(attribute(stop, "stop-color") ?? "black")
                color.a = Float(try number(stop, "stop-opacity", 1))
                let offset = Float(try number(stop, "offset", 0))
                stops.append((max(offset, stops.last?.0 ?? 0), color))
            }
            guard !stops.isEmpty else { throw RenderError("linearGradient #\(id) has no stops") }
            let dx = p2.x - p1.x, dy = p2.y - p1.y
            let length2 = dx * dx + dy * dy
            let inverse = ctm.inverted()
            return { x, y in
                let p = CGPoint(x: CGFloat(x) + 0.5, y: CGFloat(y) + 0.5).applying(inverse)
                let t = Float(((p.x - p1.x) * dx + (p.y - p1.y) * dy) / length2)
                if t <= stops[0].0 { return stops[0].1 }
                for i in 1..<stops.count where t <= stops[i].0 {
                    let (o0, c0) = stops[i - 1], (o1, c1) = stops[i]
                    let f = o1 > o0 ? (t - o0) / (o1 - o0) : 1
                    // Color and opacity interpolate separately (non-premultiplied), per SVG.
                    return RGBA(r: c0.r + (c1.r - c0.r) * f, g: c0.g + (c1.g - c0.g) * f,
                                b: c0.b + (c1.b - c0.b) * f, a: c0.a + (c1.a - c0.a) * f)
                }
                return stops[stops.count - 1].1
            }
        }
    }

    func fill(_ cov: [Float], with paint: Paint, into target: inout Layer) throws {
        let color = try shader(paint)
        for y in 0..<height {
            for x in 0..<width {
                let k = y * width + x
                let c = cov[k]
                if c <= 0 { continue }
                let s = color(x, y)
                let a = s.a * c
                let i = k * 4
                let keep = 1 - a
                target.data[i] = s.r * a + target.data[i] * keep
                target.data[i + 1] = s.g * a + target.data[i + 1] * keep
                target.data[i + 2] = s.b * a + target.data[i + 2] * keep
                target.data[i + 3] = a + target.data[i + 3] * keep
            }
        }
    }

    // MARK: Masks

    func applyMask(_ mask: XMLElement, to layer: inout Layer) throws {
        try check(mask)
        guard attribute(mask, "maskUnits") == "userSpaceOnUse" else { throw RenderError("mask must use maskUnits=userSpaceOnUse") }
        var style = Style()
        try applyPresentation(mask, to: &style)
        var content = Layer(width, height)
        for child in mask.children ?? [] {
            if let e = child as? XMLElement { try draw(e, style: style, into: &content) }
        }
        let region = try regionCoverage(mask)
        for k in 0..<layer.count {
            let i = k * 4
            // Luminance of the premultiplied mask content (sRGB coefficients), times the region.
            let luminance = 0.2125 * content.data[i] + 0.7154 * content.data[i + 1] + 0.0721 * content.data[i + 2]
            let m = luminance * region[k]
            for c in 0..<4 { layer.data[i + c] *= m }
        }
    }

    func regionCoverage(_ element: XMLElement) throws -> [Float] {
        let rect = CGRect(x: try number(element, "x"), y: try number(element, "y"),
                          width: try number(element, "width"), height: try number(element, "height"))
        return coverage(of: CGPath(rect: rect, transform: nil), transform: ctm, width: width, height: height, evenOdd: false)
    }

    // MARK: Filters

    func applyFilter(_ filter: XMLElement, source: Layer) throws -> Layer {
        guard filter.name == "filter" else { throw RenderError("not a filter") }
        for a in filter.attributes ?? [] {
            guard ["id", "x", "y", "width", "height", "filterUnits", "color-interpolation-filters"].contains(a.name ?? "") else {
                throw RenderError("unsupported attribute \(a.name ?? "") on <filter>")
            }
        }
        guard attribute(filter, "filterUnits") == "userSpaceOnUse",
              attribute(filter, "color-interpolation-filters") == "sRGB" else {
            throw RenderError("filter must use filterUnits=userSpaceOnUse and color-interpolation-filters=sRGB")
        }
        var sourceAlpha = Layer(width, height)
        for k in 0..<source.count { sourceAlpha.data[k * 4 + 3] = source.data[k * 4 + 3] }
        var results: [String: Layer] = ["SourceGraphic": source, "SourceAlpha": sourceAlpha]
        var last = source
        let s = Double(scale)

        func input(_ primitive: XMLElement, _ name: String) throws -> Layer {
            guard let key = attribute(primitive, name) else { return last }
            guard let layer = results[key] else { throw RenderError("unsupported filter input \(key)") }
            return layer
        }

        for child in filter.children ?? [] {
            guard let p = child as? XMLElement else { continue }
            guard let names = primitiveAttributes[p.name ?? ""] else {
                throw RenderError("unsupported filter primitive <\(p.name ?? "")>")
            }
            try requireOnly(names, on: p)
            var out: Layer
            switch p.name ?? "" {
            case "feFlood":
                let color = try parseColor(attribute(p, "flood-color") ?? "black")
                let alpha = Float(try number(p, "flood-opacity", 1))
                out = Layer(width, height)
                for k in 0..<out.count {
                    out.data[k * 4] = color.r * alpha; out.data[k * 4 + 1] = color.g * alpha
                    out.data[k * 4 + 2] = color.b * alpha; out.data[k * 4 + 3] = alpha
                }
            case "feColorMatrix":
                guard attribute(p, "type") == "matrix" else { throw RenderError("feColorMatrix type must be matrix") }
                let m = (attribute(p, "values") ?? "").split(whereSeparator: { $0 == " " || $0 == "," }).compactMap { Float($0) }
                guard m.count == 20 else { throw RenderError("feColorMatrix needs 20 values") }
                let i0 = try input(p, "in")
                out = Layer(width, height)
                for k in 0..<out.count {
                    let i = k * 4
                    let a = i0.data[i + 3]
                    let r = a > 0 ? i0.data[i] / a : 0, g = a > 0 ? i0.data[i + 1] / a : 0, b = a > 0 ? i0.data[i + 2] / a : 0
                    @inline(__always) func row(_ n: Int) -> Float {
                        min(1, max(0, m[n * 5] * r + m[n * 5 + 1] * g + m[n * 5 + 2] * b + m[n * 5 + 3] * a + m[n * 5 + 4]))
                    }
                    let alpha = row(3)
                    out.data[i] = row(0) * alpha; out.data[i + 1] = row(1) * alpha
                    out.data[i + 2] = row(2) * alpha; out.data[i + 3] = alpha
                }
            case "feMorphology":
                let i0 = try input(p, "in")
                let radius = Int((try number(p, "radius") * s).rounded())
                let dilate = (attribute(p, "operator") ?? "erode") == "dilate"
                out = i0
                if radius > 0 {
                    for c in 0..<4 {
                        var channel = (0..<i0.count).map { i0.data[$0 * 4 + c] }
                        if channel.allSatisfy({ $0 == 0 }) { continue }
                        var tmp = channel
                        for y in 0..<height {
                            for x in 0..<width {
                                var v: Float = dilate ? 0 : 1
                                for j in max(0, x - radius)...min(width - 1, x + radius) {
                                    let w = channel[y * width + j]
                                    v = dilate ? max(v, w) : min(v, w)
                                }
                                tmp[y * width + x] = v
                            }
                        }
                        for y in 0..<height {
                            for x in 0..<width {
                                var v: Float = dilate ? 0 : 1
                                for j in max(0, y - radius)...min(height - 1, y + radius) {
                                    let w = tmp[j * width + x]
                                    v = dilate ? max(v, w) : min(v, w)
                                }
                                channel[y * width + x] = v
                            }
                        }
                        for k in 0..<out.count { out.data[k * 4 + c] = channel[k] }
                    }
                }
            case "feOffset":
                let i0 = try input(p, "in")
                let dx = try number(p, "dx", 0) * s, dy = try number(p, "dy", 0) * s
                out = Layer(width, height)
                let ix = Int(floor(dx)), iy = Int(floor(dy))
                let fx = Float(dx - floor(dx)), fy = Float(dy - floor(dy))
                for y in 0..<height {
                    for x in 0..<width {
                        // Bilinear: out(x, y) samples in(x - dx, y - dy).
                        for c in 0..<4 {
                            func at(_ sx: Int, _ sy: Int) -> Float {
                                (sx < 0 || sy < 0 || sx >= width || sy >= height) ? 0 : i0.data[(sy * width + sx) * 4 + c]
                            }
                            let sx = x - ix, sy = y - iy
                            out.data[(y * width + x) * 4 + c] =
                                at(sx, sy) * (1 - fx) * (1 - fy) + at(sx - 1, sy) * fx * (1 - fy)
                                + at(sx, sy - 1) * (1 - fx) * fy + at(sx - 1, sy - 1) * fx * fy
                        }
                    }
                }
            case "feGaussianBlur":
                let i0 = try input(p, "in")
                let deviations = (attribute(p, "stdDeviation") ?? "0").split(separator: " ").compactMap { Double($0) }
                let sx = (deviations.first ?? 0) * s, sy = (deviations.count > 1 ? deviations[1] : deviations.first ?? 0) * s
                out = Layer(width, height)
                for c in 0..<4 {
                    let channel = (0..<i0.count).map { i0.data[$0 * 4 + c] }
                    if channel.allSatisfy({ $0 == 0 }) { continue }
                    let blurred = gaussian(channel, width: width, height: height, sigmaX: sx, sigmaY: sy)
                    for k in 0..<out.count { out.data[k * 4 + c] = blurred[k] }
                }
            case "feComposite":
                let a = try input(p, "in"), b = try input(p, "in2")
                let op = attribute(p, "operator") ?? "over"
                let k1 = Float(try number(p, "k1", 0)), k2 = Float(try number(p, "k2", 0))
                let k3 = Float(try number(p, "k3", 0)), k4 = Float(try number(p, "k4", 0))
                guard ["over", "in", "out", "atop", "xor", "arithmetic"].contains(op) else {
                    throw RenderError("unsupported feComposite operator \(op)")
                }
                out = Layer(width, height)
                for k in 0..<out.count {
                    let i = k * 4
                    let aa = a.data[i + 3], ba = b.data[i + 3]
                    @inline(__always) func composite(_ x: Float, _ y: Float) -> Float {
                        switch op {
                        case "over": return x + y * (1 - aa)
                        case "in": return x * ba
                        case "out": return x * (1 - ba)
                        case "atop": return x * ba + y * (1 - aa)
                        case "xor": return x * (1 - ba) + y * (1 - aa)
                        default: return min(1, max(0, k1 * x * y + k2 * x + k3 * y + k4))
                        }
                    }
                    let alpha = composite(aa, ba)
                    out.data[i + 3] = alpha
                    for c in 0..<3 { out.data[i + c] = min(composite(a.data[i + c], b.data[i + c]), alpha) }
                }
            case "feBlend":
                guard (attribute(p, "mode") ?? "normal") == "normal" else { throw RenderError("feBlend mode must be normal") }
                let a = try input(p, "in"), b = try input(p, "in2")
                out = b
                over(a, onto: &out)
            default:
                throw RenderError("unsupported filter primitive <\(p.name ?? "")>")
            }
            if let key = attribute(p, "result") { results[key] = out }
            last = out
        }
        // The filter region clips the result.
        let region = try regionCoverage(filter)
        for k in 0..<last.count { for c in 0..<4 { last.data[k * 4 + c] *= region[k] } }
        return last
    }

    func over(_ source: Layer, onto target: inout Layer) {
        for k in 0..<source.count {
            let i = k * 4
            let a = source.data[i + 3]
            if a <= 0 && source.data[i] <= 0 && source.data[i + 1] <= 0 && source.data[i + 2] <= 0 { continue }
            for c in 0..<4 { target.data[i + c] = source.data[i + c] + target.data[i + c] * (1 - a) }
        }
    }
}

// MARK: - Output

func writePNG(_ layer: Layer, to url: URL) throws {
    var bytes = layer.data.map { UInt8(max(0, min(255, ($0 * 255).rounded()))) }
    let context = CGContext(
        data: &bytes, width: layer.width, height: layer.height, bitsPerComponent: 8, bytesPerRow: layer.width * 4,
        space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    guard let image = context.makeImage(),
          let destination = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil)
    else { throw RenderError("cannot write \(url.path)") }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else { throw RenderError("cannot write \(url.path)") }
}

/// Averages k-by-k blocks of premultiplied pixels.
func downsample(_ layer: Layer, to pixels: Int) throws -> Layer {
    guard layer.width % pixels == 0 else { throw RenderError("\(pixels) px does not divide the \(layer.width) px render") }
    let k = layer.width / pixels
    if k == 1 { return layer }
    var out = Layer(pixels, pixels)
    let scale = 1 / Float(k * k)
    for y in 0..<pixels {
        for x in 0..<pixels {
            for c in 0..<4 {
                var sum: Float = 0
                for dy in 0..<k {
                    let row = (y * k + dy) * layer.width
                    for dx in 0..<k { sum += layer.data[(row + x * k + dx) * 4 + c] }
                }
                out.data[(y * pixels + x) * 4 + c] = sum * scale
            }
        }
    }
    return out
}

// The master is rendered once, at `--internal` pixels (2048 by default), and every output is
// a box-filtered reduction of that render. Supersampling keeps abutting antialiased edges
// (the panel's fill against its masked border) from letting the rim show through, and keeps
// filter radii in proportion at sizes where a 4-unit offset is a fraction of a pixel.
var arguments = Array(CommandLine.arguments.dropFirst())
if arguments.count >= 2, arguments[0] == "--time-limit", let seconds = UInt32(arguments[1]), seconds > 0 {
    alarm(seconds)
    arguments.removeFirst(2)
}
var renderSize = 2048
if arguments.count >= 2, arguments[0] == "--internal", let n = Int(arguments[1]) {
    renderSize = n
    arguments.removeFirst(2)
}
guard arguments.count >= 3, arguments.count % 2 == 1 else {
    FileHandle.standardError.write(Data("usage: render-svg [--time-limit SECONDS] [--internal PIXELS] MASTER.svg OUT.png PIXELS [OUT.png PIXELS ...]\n".utf8))
    exit(2)
}
do {
    let document = try Document(url: URL(fileURLWithPath: arguments[0]))
    let render = try Renderer(document: document, pixels: renderSize).render()
    for pair in stride(from: 1, to: arguments.count, by: 2) {
        guard let pixels = Int(arguments[pair + 1]), pixels > 0 else { throw RenderError("bad size \(arguments[pair + 1])") }
        try writePNG(try downsample(render, to: pixels), to: URL(fileURLWithPath: arguments[pair]))
    }
} catch {
    FileHandle.standardError.write(Data("render-svg: \(error)\n".utf8))
    exit(1)
}
