// Constructs the icon's two glyphs, a partial M (|\/) and a B, and writes them into a master
// SVG, replacing only the glyph paths, their fills, and the glyph filter's region. The rest
// of the master (squircle, rim, panel, sheen, border, and the glyphs' inner shadow) is the
// sister app's v6 icon structure, copied verbatim.
//
// Every dimension comes from Reddit Mono Bold (wght 700) at 232 px, the face and size of the
// sister app's K, in font units (2048 per em) scaled by 232/2048:
//   - The B is the font's own B outline, unedited, on the K's origin and baseline.
//   - The partial M is drawn: the B's stem width, the K's diagonal weight (the K's arms are
//     stem weight, measured perpendicular), the M's diagonal angle, the M's crotch and vertex
//     heights, flat cuts on the cap line, the baseline, and the vertex line.
//
// Usage: make-glyphs TEMPLATE.svg OUT.svg JUNCTION [GUIDES.svg]
//   JUNCTION is how the M's second diagonal meets the B's stem:
//     touch    its upper edge ends on the stem's top-left corner (the stem stays a clean
//              rectangle; the first stem gets the same corner join)
//     overlap  it runs into the stem as in the font's M (its upper edge reaches the cap line
//              inside the stem)
//     gap      it stops short with a flat top terminal, the sister app's glyph gap from the stem
import CoreGraphics
import Foundation

// MARK: - Measurements (font units unless noted)

let em = 232.0  // px: the sister app's K is Reddit Mono Bold at 232 px.
let unit = em / 2048  // px per font unit
let baseline = 339.0  // px in the 512 frame: the sister app's K baseline (Figma snaps it to 339)
let capHeight = 1474.0  // B, K, M, and N cap height
let stem = 371.828 - 94.0781  // B stem: 277.75 (the K's is 275.2, the M's 257.4)
let diagonal = stem  // K's arms measured perpendicular: 277.4 (upper) and 276.2 (leg)
let tanTheta = (572.0 - 242.094) / (1474.0 - 878.781)  // M's outer diagonal edge: 29.0 degrees from vertical
let crotchHeight = 878.781  // M: where the diagonals' upper edges meet
let vertexHeight = 481.828  // M: the flat cut under the vertex
let topFlat = (242.094 - 62.6094) / (320.0 - 62.6094)  // M: stem top before the diagonal starts, as a fraction of the stem (0.697)
let gapPx = 252.801 - 231.364  // px: the sister app's gap from its first glyph's tip to the K's stem
// The sister app's glyph pair, measured from its v6 outlines: area centroid x in the 512 frame.
// The new pair is placed with its centroid on the same x, so both marks balance alike.
let targetCentroidX = 262.598
let fills = (first: "#F1DF53", b: "#B4C0FF")  // see README: Metabrowser's JavaScript and Markdown hues

// Reddit Mono Bold (wght 700) "B", font units, y up. Copyright 2020-23 Reddit, Inc.,
// SIL Open Font License 1.1. Only these outline coordinates are used; the font is not.
let bOutline: [[Double]] = [  // M/L x y, Q cx cy x y, Z
    [347.922, 0], [347.922, 252.172], [631.828, 252.172], [711.344, 252.172, 760.148, 305.328],
    [808.953, 358.484, 808.953, 448.516], [808.953, 535.734, 758.414, 585.906], [707.875, 636.078, 624.875, 636.078],
    [341.484, 636.078], [341.484, 858.266], [564.094, 858.266], [610.172, 858.266, 645.5, 882.07],
    [680.828, 905.875, 700.719, 948.305], [720.609, 990.734, 720.609, 1045.22], [720.609, 1128.12, 675.867, 1174.98],
    [631.125, 1221.83, 559.734, 1221.83], [341.484, 1221.83], [341.484, 1474], [550.344, 1474],
    [688.516, 1474, 786.695, 1425.37], [884.875, 1376.73, 936.656, 1292.17], [988.438, 1207.61, 988.438, 1099.73],
    [988.438, 1014.34, 957.18, 939.234], [925.922, 864.125, 875.094, 809.305], [824.266, 754.484, 765.125, 730.781],
    [766, 800.781], [852.094, 782.438, 924.484, 735.656], [996.875, 688.875, 1040.52, 611.219],
    [1084.17, 533.562, 1084.17, 421.828], [1084.17, 297.172, 1028.83, 202.281], [973.484, 107.391, 876.547, 53.6953],
    [779.609, 0, 654.703, 0], [],
    [94.0781, 0], [94.0781, 1474], [371.828, 1474], [371.828, 0], [],
]
let bStemLeft = 94.0781

// MARK: - Geometry

struct Glyphs {
    var first: CGPath
    var b: CGPath
    var bOrigin: Double
    var guides: [String: Double]
}

func px(_ u: Double) -> Double { u * unit }
func y(_ heightUnits: Double) -> Double { baseline - heightUnits * unit }

func polygon(_ points: [(Double, Double)]) -> CGPath {
    let path = CGMutablePath()
    path.addLines(between: points.map { CGPoint(x: $0.0, y: $0.1) })
    path.closeSubpath()
    return path
}

func rect(_ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double) -> CGPath {
    CGPath(rect: CGRect(x: x0, y: y0, width: x1 - x0, height: y1 - y0), transform: nil)
}

func bPath(origin: Double) -> CGPath {
    let path = CGMutablePath()
    var start = true
    for item in bOutline {
        func p(_ i: Int) -> CGPoint { CGPoint(x: origin + px(item[i]), y: y(item[i + 1])) }
        switch item.count {
        case 0: path.closeSubpath(); start = true
        case 2: if start { path.move(to: p(0)); start = false } else { path.addLine(to: p(0)) }
        case 4: path.addQuadCurve(to: p(2), control: p(0))
        default: fatalError("bad outline entry")
        }
    }
    return path
}

/// The pair with the first stem's left edge at x0.
func construct(x0: Double, junction: String) -> Glyphs {
    let w = px(stem)
    let top = y(capHeight)
    let cosTheta = 1 / (1 + tanTheta * tanTheta).squareRoot()
    let hw = px(diagonal) / cosTheta  // horizontal width of a diagonal
    let a = junction == "touch" ? w : px(stem) * topFlat  // where the first diagonal's upper edge leaves the cap line
    let crotchY = y(crotchHeight), vertexY = y(vertexHeight)
    let start = x0 + a
    let xm = start + (crotchY - top) * tanTheta  // the crotch, on the M's axis
    let xB: Double  // the B's stem left edge
    switch junction {
    case "touch", "overlap": xB = 2 * xm - x0 - w  // the B's stem mirrors the first stem
    case "gap": xB = 2 * xm - (start - hw) + gapPx  // the second diagonal's top terminal, then the gap
    default: fatalError("junction must be touch, overlap, or gap")
    }

    // Each diagonal is a band between parallel edges, cut later by the cap and vertex lines.
    let y0 = top - 100, y1 = baseline + 100
    func upper(_ yy: Double) -> Double { start + (yy - top) * tanTheta }
    let left = polygon([(upper(y0) - hw, y0), (upper(y0), y0), (upper(y1), y1), (upper(y1) - hw, y1)])
    let right = polygon([(2 * xm - upper(y0) + hw, y0), (2 * xm - upper(y0), y0), (2 * xm - upper(y1), y1), (2 * xm - upper(y1) + hw, y1)])
    // The bands cross at the crotch and would go on as an X; each ends at the other's outer
    // edge, so the V is also bounded by the wedge over the point where the outer edges meet.
    let wedge = polygon([(upper(y0) - hw, y0), (2 * xm - upper(y0) + hw, y0), (xm, crotchY + hw / tanTheta)])
    let clipRight = junction == "gap" ? 10_000 : xB + 2  // hidden under the B's stem, so no antialiasing seam
    let vee = left.union(right, using: .winding)
        .intersection(wedge, using: .winding)
        .intersection(rect(x0, top, clipRight, vertexY), using: .winding)
    let first = rect(x0, top, x0 + w, baseline).union(vee, using: .winding)
    let bOrigin = xB - px(bStemLeft)
    return Glyphs(first: first, b: bPath(origin: bOrigin), bOrigin: bOrigin, guides: [
        "x0": x0, "stemRight": x0 + w, "xm": xm, "xB": xB, "xBRight": xB + w, "top": top, "baseline": baseline,
        "crotchY": crotchY, "vertexY": vertexY, "start": start, "hw": hw, "w": w, "tanTheta": tanTheta,
    ])
}

/// Area centroid x of the filled pair, by rasterizing at 16x the 512 frame.
func centroidX(_ paths: [CGPath]) -> Double {
    let s = 16, n = 512 * s
    var buffer = [UInt8](repeating: 0, count: n * n)
    let context = CGContext(data: &buffer, width: n, height: n, bitsPerComponent: 8, bytesPerRow: n,
                            space: CGColorSpaceCreateDeviceGray(), bitmapInfo: 0)!
    context.scaleBy(x: CGFloat(s), y: CGFloat(s))
    context.setFillColor(gray: 1, alpha: 1)
    for p in paths { context.addPath(p) }
    context.fillPath()
    var sum = 0.0, area = 0.0
    for row in 0..<n { for col in 0..<n {
        let v = Double(buffer[row * n + col])
        if v > 0 { sum += v * (Double(col) + 0.5) / Double(s); area += v }
    } }
    return sum / area
}

func svgPath(_ path: CGPath) -> String {
    var out = ""
    func f(_ v: CGFloat) -> String {
        var s = String(format: "%.3f", Double(v))
        while s.hasSuffix("0") { s.removeLast() }
        if s.hasSuffix(".") { s.removeLast() }
        return s == "-0" ? "0" : s
    }
    path.applyWithBlock { element in
        let e = element.pointee
        switch e.type {
        case .moveToPoint: out += "M\(f(e.points[0].x)) \(f(e.points[0].y))"
        case .addLineToPoint: out += "L\(f(e.points[0].x)) \(f(e.points[0].y))"
        case .addQuadCurveToPoint: out += "Q\(f(e.points[0].x)) \(f(e.points[0].y)) \(f(e.points[1].x)) \(f(e.points[1].y))"
        case .addCurveToPoint:
            out += "C\(f(e.points[0].x)) \(f(e.points[0].y)) \(f(e.points[1].x)) \(f(e.points[1].y)) \(f(e.points[2].x)) \(f(e.points[2].y))"
        case .closeSubpath: out += "Z"
        @unknown default: break
        }
    }
    return out
}

/// A polygonal path as SVG data, without the repeated and collinear points path booleans leave.
func polygonPath(_ path: CGPath) -> String {
    var contours: [[CGPoint]] = []
    path.applyWithBlock { element in
        let e = element.pointee
        switch e.type {
        case .moveToPoint: contours.append([e.points[0]])
        case .addLineToPoint: contours[contours.count - 1].append(e.points[0])
        case .closeSubpath: break
        default: fatalError("the partial M must be a polygon")
        }
    }
    let simplified = contours.map { points -> [CGPoint] in
        var p = points
        var changed = true
        while changed && p.count > 3 {
            changed = false
            for i in 0..<p.count {
                let a = p[(i + p.count - 1) % p.count], b = p[i], c = p[(i + 1) % p.count]
                let cross = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x)
                if hypot(b.x - a.x, b.y - a.y) < 1e-4 || abs(cross) < 1e-6 {
                    p.remove(at: i)
                    changed = true
                    break
                }
            }
        }
        return p
    }
    let out = CGMutablePath()
    for points in simplified {
        out.addLines(between: points)
        out.closeSubpath()
    }
    return svgPath(out)
}

// MARK: - Output

let arguments = CommandLine.arguments
guard arguments.count == 4 || arguments.count == 5 else {
    FileHandle.standardError.write(Data("usage: make-glyphs TEMPLATE.svg OUT.svg touch|overlap|gap [GUIDES.svg]\n".utf8))
    exit(2)
}
let junction = arguments[3]
let trial = construct(x0: 0, junction: junction)
let firstVisible = junction == "gap" ? trial.first
    : trial.first.intersection(rect(-1000, 0, trial.guides["xB"]!, 512), using: .winding)
let shift = targetCentroidX - centroidX([firstVisible, trial.b])
let glyphs = construct(x0: shift, junction: junction)
let g = glyphs.guides

let bounds = glyphs.first.boundingBoxOfPath.union(glyphs.b.boundingBoxOfPath)
var svg = try String(contentsOfFile: arguments[1], encoding: .utf8)
// The glyph group is the one <g> whose filter is the inner shadow (Figma names it filter1_i_*).
let groupPattern = try NSRegularExpression(pattern: #"(<g filter="url\(#(filter1_i_[^)"]+)\)">\n)(.*?)(\n</g>)"#, options: [.dotMatchesLineSeparators])
guard let match = groupPattern.firstMatch(in: svg, range: NSRange(svg.startIndex..., in: svg)),
      let idRange = Range(match.range(at: 2), in: svg) else {
    FileHandle.standardError.write(Data("make-glyphs: no glyph group in \(arguments[1])\n".utf8))
    exit(1)
}
let filterID = String(svg[idRange])
let paths = """
<path d="\(polygonPath(glyphs.first))" fill="\(fills.first)"/>
<path d="\(svgPath(glyphs.b))" fill="\(fills.b)"/>
"""
let mutable = NSMutableString(string: svg)
groupPattern.replaceMatches(in: mutable, range: NSRange(location: 0, length: mutable.length), withTemplate: "$1\(NSRegularExpression.escapedTemplate(for: paths))$4")
svg = mutable as String
// Figma sizes the inner-shadow filter to the glyphs' bounds plus 3 px right and below.
func f3(_ v: Double) -> String { String(format: "%.3f", v) }
let filterPattern = try NSRegularExpression(pattern: #"<filter id="\#(filterID)" x="[^"]*" y="[^"]*" width="[^"]*" height="[^"]*""#)
let region = #"<filter id="\#(filterID)" x="\#(f3(bounds.minX))" y="\#(f3(bounds.minY))" width="\#(f3(bounds.width + 3))" height="\#(f3(bounds.height + 3))""#
let replaced = filterPattern.stringByReplacingMatches(in: svg, range: NSRange(svg.startIndex..., in: svg), withTemplate: NSRegularExpression.escapedTemplate(for: region))
guard filterPattern.firstMatch(in: svg, range: NSRange(svg.startIndex..., in: svg)) != nil else {
    FileHandle.standardError.write(Data("make-glyphs: no filter #\(filterID)\n".utf8))
    exit(1)
}
try replaced.write(toFile: arguments[2], atomically: true, encoding: .utf8)

// Construction guides: cap line, baseline, crotch and vertex lines, stem edges, the M's axis,
// and both diagonals' edges extended.
if arguments.count == 5 {
    let top = g["top"]!, base = g["baseline"]!, hw = g["hw"]!, start = g["start"]!, xm = g["xm"]!
    func line(_ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double, _ color: String) -> String {
        #"<path d="M\#(f3(x0)) \#(f3(y0))L\#(f3(x1)) \#(f3(y1))" stroke="\#(color)" stroke-width="0.6"/>"#
    }
    var lines: [String] = []
    for key in ["top", "baseline", "crotchY", "vertexY"] { lines.append(line(110, g[key]!, 402, g[key]!, "#00D8FF")) }
    for key in ["x0", "stemRight", "xB", "xBRight"] { lines.append(line(g[key]!, 140, g[key]!, 372, "#00D8FF")) }
    lines.append(line(xm, 140, xm, 372, "#FF5C8A"))
    let ya = top - 40, yb = base + 20
    for offset in [0.0, -hw] {
        let u0 = start + offset + (ya - top) * tanTheta, u1 = start + offset + (yb - top) * tanTheta
        lines.append(line(u0, ya, u1, yb, "#FF5C8A"))
        lines.append(line(2 * xm - u0, ya, 2 * xm - u1, yb, "#FF5C8A"))
    }
    let guides = """
    <svg width="512" height="512" viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
    \(lines.joined(separator: "\n"))
    </svg>

    """
    try guides.write(toFile: arguments[4], atomically: true, encoding: .utf8)
}

print(String(format: """
junction %@: stem %.3f px, diagonal %.3f px (horizontal %.3f), angle %.2f deg, cap %.3f, baseline %.3f, \
crotch %.3f, vertex %.3f, first stem x %.3f-%.3f, axis %.3f, B stem x %.3f-%.3f, B origin %.3f, \
ink x %.3f-%.3f (center %.3f), centroid placed at %.3f
""", junction, g["w"]!, px(diagonal), g["hw"]!, atan(tanTheta) * 180 / .pi, g["top"]!, g["baseline"]!,
      g["crotchY"]!, g["vertexY"]!, g["x0"]!, g["stemRight"]!, g["xm"]!, g["xB"]!, g["xBRight"]!, glyphs.bOrigin,
      bounds.minX, bounds.maxX, bounds.midX, targetCentroidX))
