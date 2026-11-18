// Builds an icon master from a parameter file: it copies the variant's base (the sister app's
// v6 icon structure, base-release.svg or base-dev.svg) and fills its glyph group with a
// partial M (|\/) and a B, sized and placed by the parameters. Nothing else changes.
//
// Every parameter has a default, today's value, documented in Params below and in README.md.
// A parameter file lists the parameters it sets; unknown names are refused. The values are in
// units of the 512-unit master; the font measurements are Reddit Mono Bold (wght 700) at
// 232 px, the face and size of the sister app's K, in font units (2048 per em) times 232/2048.
//
// Usage: make-glyphs PARAMS.json OUT.svg [--guides GUIDES.svg] [--dims DIMS]
//                    [--fills FIRST,B] [--junction NAME] [--swift MARK.swift]
//   --guides writes the construction lines as an SVG overlay; --dims writes the derived
//   dimensions as shell assignments; --fills and --junction override the parameter file, for
//   comparison sheets; --swift writes the mark alone, the glyph group's path data and fills
//   as the master has them, as Swift for the app's title bar (AppIconMarkGeometry.swift).
import CoreGraphics
import Foundation

// MARK: - Parameters

struct Params: Decodable {
    /// The base: "release" (base-release.svg) or "dev" (base-dev.svg, the sister app's canary
    /// scheme).
    var variant = "release"
    /// How the M's rising diagonal meets the B's stem:
    ///   "gap"          the diagonal ends at a vertical face, then `gap`, then the B's stem;
    ///   "bevel"        the B's stem stands where the M's right stem would; the diagonal runs to
    ///                  the cap line over it, and the B is cut by a line parallel to it, `gap`
    ///                  away;
    ///   "b-over"       the same placement with the B intact; the diagonal ends at a vertical
    ///                  face `gap` left of the B's stem;
    ///   "corner-bevel" the diagonal runs to the cap line and the B's top-left corner is cut
    ///                  parallel to it, `gap` away; `cornerCut` sizes the corner and so places
    ///                  the B;
    ///   "touch"        the diagonal's upper edge ends on the B stem's top-left corner;
    ///   "overlap"      the diagonal runs into the B's stem as in the font's M;
    ///   "no-rise"      there is no rising diagonal: the partial M is |\, the falling diagonal
    ///                  ends at cuts lined up with the B's middle bar (`endFace`, `endFloor`),
    ///                  and the B's stem follows `gap` beyond the end's rightmost point.
    var junction = "gap"
    /// The space between the partial M and the B: from the vertical face to the B's stem
    /// ("gap"), or the channel between the diagonal and the B's bevel ("bevel"). Default: the
    /// sister app's least distance between its glyphs, its chevron's tip to its K's stem.
    var gap = 21.437
    /// "perpendicular" (square to the diagonal) or "horizontal". Matters only for the bevels:
    /// the other junctions' facing edges are both vertical.
    var gapMeasure = "perpendicular"
    /// "corner-bevel" junction: how far the corner cut runs along the B's cap line, in B stems.
    /// The cut runs down the stem's left edge 1/tan(angle) times as far. Below 0.779 (the
    /// channel's width across, in stems) the diagonal stops short of the B's stem; above it the
    /// diagonal reaches over the stem.
    var cornerCut = 0.5
    /// "gap" junction: the width of the diagonal's flat top, in stems, which places the vertical
    /// face. 1 puts the face where the first stem's outer edge falls mirrored on the M's axis; 0
    /// puts it where the diagonal's upper edge meets the cap line, so the diagonal ends in a point
    /// on the cap line.
    var faceTopFlat = 1.0
    /// "gap" junction, with `faceTopFlat` 0: how far below the cap line the vertical face's top
    /// sits. The face moves left with it, the diagonal ends there in a point as sharp as `angle`,
    /// and the B's stem still follows `gap` beyond the face.
    var faceDrop = 0.0
    /// "no-rise" junction: the line of the B's middle bar at which a vertical cut meets the
    /// falling diagonal's upper edge, placing the end's vertical face: "barTop", "barCenter",
    /// "barBottom", or "none" for no vertical cut.
    var endFace = "none"
    /// "no-rise" junction: the horizontal cut under the falling diagonal's end: "barTop",
    /// "barCenter", or "barBottom" (lines of the B's middle bar), or "vertex" (`vertexFlat`, where
    /// the M's V is cut).
    var endFloor = "vertex"
    /// The partial M's stem. Default: the font's B stem, 277.75 font units (the B itself keeps
    /// the font's stem whatever this says).
    var stem = 31.464
    /// The diagonals' thickness, square to the stroke. Default: the K's arms, stem weight.
    var diagonal = 31.464
    /// The diagonals' angle from vertical, in degrees. Default: the font M's outer diagonal edge.
    var angle = 28.9993
    /// The cap line and baseline, as y in the master. Default: the sister app's K.
    var capLine = 172.023
    var baseline = 339.0
    /// The crotch (where the diagonals' upper edges meet) and the flat cut under the vertex, as
    /// y in the master. Default: the font M's, 878.781 and 481.828 font units above the baseline.
    var crotch = 239.451
    var vertexFlat = 284.418
    /// The pair is placed with its area centroid at this x. Default: the sister app's glyph
    /// pair, so both marks balance alike.
    var centroidX = 262.598
    /// The B's size in px per em (the font's B outline, unedited). Default: the sister app's K.
    var bSize = 232.0
    /// "overlap" junction: the stem top left before the diagonal starts, as a fraction of the
    /// stem. Default: the font M's.
    var overlapTopFlat = 0.697
    /// The thinnest part a cut may leave. A thinner wedge of the B's stem is trimmed ("bevel"),
    /// and parameters that would leave a thinner flat or a smaller fragment are refused.
    var minSliver = 6.0
    /// The two fills, as #RRGGBB or oklch(L% C H). Default: citrine and amethyst (README).
    var fills = Fills()

    struct Fills: Decodable {
        var first = "#ECC44B"
        var b = "#C896FF"
    }

    enum CodingKeys: String, CodingKey, CaseIterable {
        case variant, junction, gap, gapMeasure, cornerCut, faceTopFlat, faceDrop, endFace, endFloor, stem, diagonal
        case angle, capLine, baseline, crotch, vertexFlat, centroidX, bSize, overlapTopFlat, minSliver, fills
    }

    init() {}
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        func get<T: Decodable>(_ key: CodingKeys, _ value: inout T) throws {
            if let v = try c.decodeIfPresent(T.self, forKey: key) { value = v }
        }
        try get(.variant, &variant); try get(.junction, &junction); try get(.gap, &gap)
        try get(.gapMeasure, &gapMeasure); try get(.cornerCut, &cornerCut)
        try get(.faceTopFlat, &faceTopFlat); try get(.faceDrop, &faceDrop)
        try get(.endFace, &endFace); try get(.endFloor, &endFloor); try get(.stem, &stem)
        try get(.diagonal, &diagonal); try get(.angle, &angle); try get(.capLine, &capLine)
        try get(.baseline, &baseline); try get(.crotch, &crotch); try get(.vertexFlat, &vertexFlat)
        try get(.centroidX, &centroidX); try get(.bSize, &bSize); try get(.overlapTopFlat, &overlapTopFlat)
        try get(.minSliver, &minSliver)
        if c.contains(.fills) {
            let f = try c.nestedContainer(keyedBy: FillKeys.self, forKey: .fills)
            if let v = try f.decodeIfPresent(String.self, forKey: .first) { fills.first = v }
            if let v = try f.decodeIfPresent(String.self, forKey: .b) { fills.b = v }
        }
    }
    enum FillKeys: String, CodingKey { case first, b }
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data("make-glyphs: \(message)\n".utf8))
    exit(1)
}

// MARK: - Reddit Mono Bold "B"

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
let bStemLeft = 94.0781, bStemRight = 371.828
let bMiddleBarTop = 858.266  // the top counter's floor
let bMiddleBarBottom = 636.078  // the bottom counter's ceiling

// MARK: - Geometry

func polygon(_ points: [(Double, Double)]) -> CGPath {
    let path = CGMutablePath()
    path.addLines(between: points.map { CGPoint(x: $0.0, y: $0.1) })
    path.closeSubpath()
    return path
}

func rect(_ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double) -> CGPath {
    CGPath(rect: CGRect(x: x0, y: y0, width: x1 - x0, height: y1 - y0), transform: nil)
}

struct Glyphs {
    var first: CGPath
    var b: CGPath
    var dims: [(String, Double)]
    var notes: [String]
    func dim(_ key: String) -> Double { dims.first { $0.0 == key }!.1 }
}

/// The pair with the first stem's left edge at x0.
func construct(_ p: Params, x0: Double) -> Glyphs {
    let unit = p.bSize / 2048
    let w = p.stem
    let top = p.capLine
    let tanTheta = tan(p.angle * .pi / 180)
    let cosTheta = cos(p.angle * .pi / 180)
    let hw = p.diagonal / cosTheta  // horizontal width of a diagonal
    let a = p.junction == "overlap" ? w * p.overlapTopFlat : w  // where the first diagonal leaves the cap line
    let start = x0 + a
    let xm = start + (p.crotch - top) * tanTheta  // the crotch, on the M's axis
    let bStem = (bStemRight - bStemLeft) * unit
    var notes: [String] = []
    var dims: [(String, Double)] = []

    guard ["perpendicular", "horizontal"].contains(p.gapMeasure) else { fail("gapMeasure must be perpendicular or horizontal") }
    let across = p.gapMeasure == "perpendicular" ? p.gap / cosTheta : p.gap  // a bevel channel, measured across
    let xB: Double  // the B's stem left edge
    var clipRight = 100_000.0  // the partial M's right limit
    var floorY = p.vertexFlat  // "no-rise": the cut under the falling diagonal's end
    switch p.junction {
    case "touch", "overlap", "bevel", "b-over":
        xB = 2 * xm - x0 - w  // the B's stem where the M's right stem would be
        if p.junction == "touch" || p.junction == "overlap" { clipRight = xB + 2 }  // hidden under the B's stem: no antialiasing seam
        if p.junction == "b-over" {
            clipRight = xB - p.gap
            // The face spans the rising diagonal between its edges' crossings of x = clipRight.
            let faceTop = top + (2 * xm - start - clipRight) / tanTheta
            let faceBottom = top + (2 * xm - start + hw - clipRight) / tanTheta
            dims.append(("faceTop", max(top, faceTop)))
            dims.append(("faceBottom", faceBottom))
            dims.append(("rightEdge", clipRight))
            if faceTop > top {
                notes.append(String(format: "the cut lies %.3f left of where the rising diagonal meets the cap line, so the diagonal keeps no flat top: it ends %.3f below the cap line in a %.1f-degree point", 2 * xm - start - clipRight, faceTop - top, p.angle))
            }
            notes.append(String(format: "the vertical face runs from y %.3f to %.3f, %.3f tall; the rising diagonal keeps %.3f of its %.3f height above the crotch, and %.3f across right of the axis", max(top, faceTop), faceBottom, faceBottom - max(top, faceTop), max(0, p.crotch - faceTop), p.crotch - top, clipRight - xm))
            let flatHalf = (p.crotch + hw / tanTheta - p.vertexFlat) * tanTheta
            if clipRight < xm + flatHalf { notes.append("the cut reaches into the vertex flat") }
            guard clipRight - xm >= p.minSliver else { fail("the cut leaves the rising diagonal under minSliver across") }
        }
    case "corner-bevel":
        let cut = p.cornerCut * (bStemRight - bStemLeft) * unit
        guard cut >= p.minSliver else { fail("cornerCut leaves a corner cut under minSliver") }
        // The diagonal's upper edge meets the cap line at 2xm - start, its lower edge hw later,
        // the bevel `across` after that, and the bevel meets the cap line `cut` inside the stem.
        xB = 2 * xm - start + hw + across - cut
        dims.append(("cornerCut", cut))
        dims.append(("cornerCutDown", cut / tanTheta))
        notes.append(String(format: "the corner cut takes a triangle %.3f along the cap line and %.3f down the stem's left edge", cut, cut / tanTheta))
        let reach = 2 * xm - start + hw - xB
        notes.append(reach < 0
            ? String(format: "the diagonal's top stops %.3f short of the B's stem", -reach)
            : String(format: "the diagonal's top reaches %.3f over the B's stem", reach))
    case "gap":
        let flat = p.faceTopFlat * w
        guard p.faceTopFlat >= 0 else { fail("faceTopFlat must be 0 or more; faceDrop moves the face below the cap line") }
        guard flat == 0 || flat >= p.minSliver else {
            fail(String(format: "faceTopFlat leaves a top flat of %.3f, under minSliver %.3f; 0 ends the diagonal in a point on the cap line", flat, p.minSliver))
        }
        guard flat <= hw else { fail("faceTopFlat \(p.faceTopFlat) puts the face past the diagonal's top (\(hw) wide)") }
        guard p.faceDrop >= 0 else { fail("faceDrop must be 0 or more; a flat top is faceTopFlat") }
        guard p.faceDrop == 0 || flat == 0 else {
            fail("faceDrop puts the face below the cap line, where the diagonal keeps no flat top: set faceTopFlat to 0")
        }
        clipRight = 2 * xm - start + flat  // the diagonal's upper edge meets the cap line at 2xm - start
        if p.faceDrop > 0 { clipRight -= p.faceDrop * tanTheta }  // the upper edge falls 1/tan per unit left
        xB = clipRight + p.gap
        let faceTop = top + p.faceDrop
        let faceBottom = faceTop + (hw - flat) / tanTheta  // where the lower edge crosses the face
        guard clipRight - xm >= p.minSliver else { fail("faceDrop leaves the rising diagonal under minSliver across right of the axis") }
        guard faceBottom < p.vertexFlat else {
            fail(String(format: "faceDrop %.3f puts the face's foot at y %.3f, into the vertex flat (y %.3f)", p.faceDrop, faceBottom, p.vertexFlat))
        }
        dims.append(("faceTop", faceTop))
        dims.append(("faceBottom", faceBottom))
        dims.append(("rightEdge", clipRight))
        dims.append(("topFlat", flat))
        if flat == 0 {
            notes.append(String(format: "the diagonal keeps no flat top: it ends %.3f below the cap line in a %.1f-degree point", p.faceDrop, p.angle))
        } else {
            notes.append(String(format: "the diagonal's flat top is %.3f wide and meets the face at a right angle", flat))
        }
        notes.append(String(format: "the vertical face runs from y %.3f to %.3f, %.3f tall, %.3f right of the axis", faceTop, faceBottom, faceBottom - faceTop, clipRight - xm))
    case "no-rise":
        // The B's middle bar, as placed: between the bottom counter's ceiling and the top counter's floor.
        let barTop = p.baseline - bMiddleBarTop * unit, barBottom = p.baseline - bMiddleBarBottom * unit
        let bar = ["barTop": barTop, "barCenter": (barTop + barBottom) / 2, "barBottom": barBottom]
        guard let floorLine = p.endFloor == "vertex" ? p.vertexFlat : bar[p.endFloor] else {
            fail("endFloor must be barTop, barCenter, barBottom, or vertex")
        }
        guard p.endFace == "none" || bar[p.endFace] != nil else { fail("endFace must be barTop, barCenter, barBottom, or none") }
        guard floorLine <= p.vertexFlat else { fail(String(format: "endFloor %@ (y %.3f) lies under the vertex flat (y %.3f)", p.endFloor, floorLine, p.vertexFlat)) }
        floorY = floorLine
        func fallingUpper(_ yy: Double) -> Double { start + (yy - top) * tanTheta }
        // The diagonal's lower edge leaves the stem's right edge at top + hw/tan; above that a floor
        // would leave a flag on the stem, and just below it a notch too thin to read.
        let notch = fallingUpper(floorLine) - hw - start
        guard notch >= p.minSliver else {
            fail(notch <= 0
                ? String(format: "endFloor %@ (y %.3f) is above where the diagonal leaves the stem (y %.3f): the end would be a flag on the stem", p.endFloor, floorLine, top + hw / tanTheta)
                : String(format: "endFloor %@ (y %.3f) leaves a notch %.3f wide between the diagonal and the stem, under minSliver", p.endFloor, floorLine, notch))
        }
        let rightmost: Double
        var bottom = floorLine
        if let faceY = bar[p.endFace] {
            guard faceY < floorLine - p.minSliver else {
                fail(String(format: "endFace %@ (y %.3f) leaves a face under minSliver above endFloor %@ (y %.3f)", p.endFace, faceY, p.endFloor, floorLine))
            }
            clipRight = fallingUpper(faceY)
            rightmost = clipRight
            let point = faceY + hw / tanTheta  // where the lower edge crosses the face
            let floorWidth = clipRight - (fallingUpper(floorLine) - hw)
            guard floorWidth <= 0 || floorWidth >= p.minSliver else {
                fail(String(format: "endFace %@ and endFloor %@ leave a floor %.3f wide, under minSliver", p.endFace, p.endFloor, floorWidth))
            }
            bottom = min(floorLine, point)
            dims.append(("endFaceTop", faceY))
            dims.append(("endFaceBottom", bottom))
            dims.append(("endFloorWidth", max(0, floorWidth)))
            notes.append(point <= floorLine
                ? String(format: "the vertical end face runs from y %.3f to %.3f, %.3f tall, and ends in a %.1f-degree point", faceY, point, point - faceY, p.angle)
                : String(format: "the vertical end face runs from y %.3f to %.3f, %.3f tall, over a floor %.3f wide", faceY, floorLine, floorLine - faceY, floorWidth))
        } else {
            rightmost = fallingUpper(floorLine)
            dims.append(("endFloorWidth", hw))
            notes.append(String(format: "the end is a horizontal cut %.3f wide at y %.3f; its right corner, %.1f degrees, comes nearest the B", hw, floorLine, 90 - p.angle))
        }
        xB = rightmost + p.gap
        dims.append(("barTop", barTop))
        dims.append(("barCenter", (barTop + barBottom) / 2))
        dims.append(("barBottom", barBottom))
        dims.append(("barThickness", barBottom - barTop))
        dims.append(("endFloor", floorLine))
        dims.append(("endBottom", bottom))
        dims.append(("notch", notch))
        dims.append(("rightEdge", rightmost))
        notes.append(String(format: "the falling diagonal ends at y %.3f, %.3f below the crotch and %.3f above the vertex flat; the notch under it is %.3f wide", bottom, bottom - p.crotch, p.vertexFlat - bottom, notch))
        notes.append(String(format: "the B's middle bar runs from y %.3f to %.3f (%.3f thick); the B's stem stands %.3f beyond the end's rightmost point (x %.3f)", barTop, barBottom, barBottom - barTop, p.gap, rightmost))
    default: fail("junction must be gap, bevel, b-over, corner-bevel, touch, overlap, or no-rise")
    }

    // Each diagonal is a band between parallel edges, cut by the cap line and the vertex flat.
    let y0 = top - 200, y1 = p.baseline + 200
    func upper(_ yy: Double) -> Double { start + (yy - top) * tanTheta }  // the falling diagonal's upper edge
    func risingLower(_ yy: Double) -> Double { 2 * xm - upper(yy) + hw }  // the rising diagonal's lower edge
    let left = polygon([(upper(y0) - hw, y0), (upper(y0), y0), (upper(y1), y1), (upper(y1) - hw, y1)])
    let right = polygon([(risingLower(y0), y0), (2 * xm - upper(y0), y0), (2 * xm - upper(y1), y1), (risingLower(y1), y1)])
    // The bands cross at the crotch and would go on as an X; each ends at the other's outer
    // edge, so the V is also bounded by the wedge over the point where the outer edges meet.
    let wedge = polygon([(upper(y0) - hw, y0), (risingLower(y0), y0), (xm, p.crotch + hw / tanTheta)])
    let vee = p.junction == "no-rise"
        ? left.intersection(rect(x0, top, clipRight, floorY), using: .winding)  // |\ alone
        : left.union(right, using: .winding)
            .intersection(wedge, using: .winding)
            .intersection(rect(x0, top, clipRight, p.vertexFlat), using: .winding)
    let first = rect(x0, top, x0 + w, p.baseline).union(vee, using: .winding)

    // The B: the font's outline on the baseline, its stem's left edge at xB.
    let bOrigin = xB - bStemLeft * unit
    let bm = CGMutablePath()
    var open = true
    for item in bOutline {
        func pt(_ i: Int) -> CGPoint { CGPoint(x: bOrigin + item[i] * unit, y: p.baseline - item[i + 1] * unit) }
        switch item.count {
        case 0: bm.closeSubpath(); open = true
        case 2: if open { bm.move(to: pt(0)); open = false } else { bm.addLine(to: pt(0)) }
        default: bm.addQuadCurve(to: pt(2), control: pt(0))
        }
    }
    var b: CGPath = bm

    if p.junction == "bevel" || p.junction == "corner-bevel" {
        let shift = across
        func bevel(_ yy: Double) -> Double { risingLower(yy) + shift }
        let keep = polygon([(bevel(y0), y0), (100_000, y0), (100_000, y1), (bevel(y1), y1)])
        b = b.intersection(keep, using: .winding)
        // Above the B's middle bar, its stem would survive only as a wedge between the bevel
        // and the top counter; trim it there, on the font's axes.
        let middleTop = p.baseline - bMiddleBarTop * unit
        let wedgeBase = xB + bStem - bevel(middleTop)
        if wedgeBase > 0 && wedgeBase < bStem {
            b = b.subtracting(rect(xB - 1, top - 1, xB + bStem, middleTop), using: .winding)
            notes.append(String(format: "trimmed the B's stem above its middle bar (y %.3f): the bevel left a wedge %.3f wide at its base", middleTop, wedgeBase))
        }
        let crossLeft = top + (risingLower(top) + shift - xB) / tanTheta
        guard crossLeft < p.baseline - p.minSliver else { fail("the bevel cuts the B's stem down to the baseline") }
        dims.append(("channel", p.gapMeasure == "perpendicular" ? p.gap : p.gap * cosTheta))
        dims.append(("bStemTop", top))
        dims.append(("channelHorizontal", shift))
        dims.append(("diagonalTopRight", risingLower(top)))
        dims.append(("bevelAtCap", bevel(top)))
        dims.append(("bevelMeetsStemRight", top + (risingLower(top) + shift - xB - bStem) / tanTheta))
        dims.append(("bevelMeetsStemLeft", crossLeft))
        dims.append(("middleBarTop", middleTop))
    }

    dims = [("x0", x0), ("stemRight", x0 + w), ("xm", xm), ("xB", xB), ("xBRight", xB + bStem), ("top", top),
            ("baseline", p.baseline), ("crotchY", p.crotch), ("vertexY", p.vertexFlat), ("start", start), ("hw", hw),
            ("w", w), ("tanTheta", tanTheta), ("bOrigin", bOrigin)] + dims
    if !dims.contains(where: { $0.0 == "rightEdge" }) { dims.append(("rightEdge", min(clipRight, xB))) }
    return Glyphs(first: first, b: b, dims: dims, notes: notes)
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

/// Areas of a path's separate pieces, in square units, by rasterizing at 8x.
func pieceAreas(_ path: CGPath) -> [Double] {
    let s = 8, n = 512 * s
    var buffer = [UInt8](repeating: 0, count: n * n)
    let context = CGContext(data: &buffer, width: n, height: n, bitsPerComponent: 8, bytesPerRow: n,
                            space: CGColorSpaceCreateDeviceGray(), bitmapInfo: 0)!
    context.scaleBy(x: CGFloat(s), y: CGFloat(s))
    context.setFillColor(gray: 1, alpha: 1)
    context.addPath(path)
    context.fillPath()
    var seen = [Bool](repeating: false, count: n * n)
    var areas: [Double] = []
    for startIndex in 0..<(n * n) where buffer[startIndex] > 127 && !seen[startIndex] {
        var stack = [startIndex], count = 0
        seen[startIndex] = true
        while let i = stack.popLast() {
            count += 1
            let x = i % n, y = i / n
            for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
                let nx = x + dx, ny = y + dy
                guard nx >= 0, ny >= 0, nx < n, ny < n else { continue }
                let j = ny * n + nx
                if buffer[j] > 127 && !seen[j] { seen[j] = true; stack.append(j) }
            }
        }
        areas.append(Double(count) / Double(s * s))
    }
    return areas
}

// MARK: - Colors

/// #RRGGBB as given, or oklch(L% C H) converted to sRGB hex.
func hexColor(_ text: String) -> String {
    let value = text.trimmingCharacters(in: .whitespaces)
    if value.hasPrefix("#"), value.count == 7, UInt32(value.dropFirst(), radix: 16) != nil { return value.uppercased() }
    guard value.hasPrefix("oklch("), value.hasSuffix(")") else { fail("fill \(text) is neither #RRGGBB nor oklch(L% C H)") }
    let parts = value.dropFirst(6).dropLast().split(separator: " ").map(String.init)
    guard parts.count == 3, let l0 = Double(parts[0].replacingOccurrences(of: "%", with: "")),
          let c = Double(parts[1]), let h = Double(parts[2]) else { fail("cannot read \(text)") }
    let l = parts[0].hasSuffix("%") ? l0 / 100 : l0
    let A = c * cos(h * .pi / 180), B = c * sin(h * .pi / 180)
    let l_ = pow(l + 0.3963377774 * A + 0.2158037573 * B, 3)
    let m_ = pow(l - 0.1055613458 * A - 0.0638541728 * B, 3)
    let s_ = pow(l - 0.0894841775 * A - 1.2914855480 * B, 3)
    let linear = [4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
                  -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
                  -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_]
    guard linear.allSatisfy({ $0 >= -0.0005 && $0 <= 1.0005 }) else { fail("\(text) is outside sRGB") }
    let bytes = linear.map { v -> Int in
        let c = min(1, max(0, v))
        return Int(((c <= 0.0031308 ? 12.92 * c : 1.055 * pow(c, 1 / 2.4) - 0.055) * 255).rounded())
    }
    return String(format: "#%02X%02X%02X", bytes[0], bytes[1], bytes[2])
}

// MARK: - SVG output

func number(_ v: CGFloat) -> String {
    var s = String(format: "%.3f", Double(v))
    while s.hasSuffix("0") { s.removeLast() }
    if s.hasSuffix(".") { s.removeLast() }
    return s == "-0" ? "0" : s
}

func svgPath(_ path: CGPath) -> String {
    var out = ""
    path.applyWithBlock { element in
        let e = element.pointee
        func p(_ i: Int) -> String { "\(number(e.points[i].x)) \(number(e.points[i].y))" }
        switch e.type {
        case .moveToPoint: out += "M\(p(0))"
        case .addLineToPoint: out += "L\(p(0))"
        case .addQuadCurveToPoint: out += "Q\(p(0)) \(p(1))"
        case .addCurveToPoint: out += "C\(p(0)) \(p(1)) \(p(2))"
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
        default: fail("the partial M must be a polygon")
        }
    }
    let out = CGMutablePath()
    for points in contours {
        var p = points
        var changed = true
        while changed && p.count > 3 {
            changed = false
            for i in 0..<p.count {
                let a = p[(i + p.count - 1) % p.count], b = p[i], c = p[(i + 1) % p.count]
                let ab = hypot(b.x - a.x, b.y - a.y), bc = hypot(c.x - b.x, c.y - b.y)
                let cross = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x)
                if ab < 1e-4 || abs(cross) < 1e-6 * ab * bc { p.remove(at: i); changed = true; break }
            }
        }
        out.addLines(between: p)
        out.closeSubpath()
    }
    return svgPath(out)
}

// MARK: - Main

var arguments = Array(CommandLine.arguments.dropFirst())
var options: [String: String] = [:]
while let flag = arguments.firstIndex(where: { $0.hasPrefix("--") }), flag + 1 < arguments.count {
    options[arguments[flag]] = arguments[flag + 1]
    arguments.removeSubrange(flag...(flag + 1))
}
guard arguments.count == 2, Set(options.keys).isSubset(of: ["--guides", "--dims", "--fills", "--junction", "--swift"]) else {
    FileHandle.standardError.write(Data(
        "usage: make-glyphs PARAMS.json OUT.svg [--guides GUIDES.svg] [--dims DIMS] [--fills FIRST,B] [--junction NAME] [--swift MARK.swift]\n".utf8))
    exit(2)
}
let paramsURL = URL(fileURLWithPath: arguments[0])
let raw = try Data(contentsOf: paramsURL)
if let object = try JSONSerialization.jsonObject(with: raw) as? [String: Any] {
    let known = Set(Params.CodingKeys.allCases.map(\.rawValue))
    for key in object.keys where !known.contains(key) && !key.hasPrefix("_") { fail("unknown parameter \(key)") }
}
var params = try JSONDecoder().decode(Params.self, from: raw)
if let j = options["--junction"] { params.junction = j }
if let f = options["--fills"] {
    let pair = f.split(separator: ",").map(String.init)
    guard pair.count == 2 else { fail("--fills takes FIRST,B") }
    params.fills = Params.Fills(first: pair[0], b: pair[1])
}

// Validate the shape before building it.
guard ["release", "dev"].contains(params.variant) else { fail("variant must be release or dev") }
guard params.stem > 0, params.diagonal > 0, params.gap >= 0, params.bSize > 0 else { fail("sizes must be positive") }
guard params.angle > 0 && params.angle < 60 else { fail("angle must be between 0 and 60 degrees") }
guard params.capLine < params.crotch, params.crotch < params.vertexFlat, params.vertexFlat < params.baseline else {
    fail("expected capLine < crotch < vertexFlat < baseline")
}
let fills = (first: hexColor(params.fills.first), b: hexColor(params.fills.b))

let trial = construct(params, x0: 0)
func visibleFirst(_ g: Glyphs) -> CGPath {
    ["touch", "overlap"].contains(params.junction)
        ? g.first.intersection(rect(-1000, 0, g.dim("xB"), 512), using: .winding) : g.first
}
let glyphs = construct(params, x0: params.centroidX - centroidX([visibleFirst(trial), trial.b]))
for (name, path) in [("partial M", visibleFirst(glyphs)), ("B", glyphs.b)] {
    if let small = pieceAreas(path).first(where: { $0 < params.minSliver * params.minSliver }) {
        fail(String(format: "the %@ has a fragment of %.1f square units, under minSliver squared", name, small))
    }
}

let base = paramsURL.deletingLastPathComponent().appendingPathComponent("base-\(params.variant).svg")
var svg = try String(contentsOf: base, encoding: .utf8)
let groupPattern = try NSRegularExpression(pattern: #"(<g filter="url\(#(filter1_i_[^)"]+)\)">\n)(.*?)(\n</g>)"#,
                                           options: [.dotMatchesLineSeparators])
guard let match = groupPattern.firstMatch(in: svg, range: NSRange(svg.startIndex..., in: svg)),
      let idRange = Range(match.range(at: 2), in: svg) else { fail("no glyph group in \(base.path)") }
let filterID = String(svg[idRange])
let firstData = polygonPath(glyphs.first), bData = svgPath(glyphs.b)
let paths = """
<path d="\(firstData)" fill="\(fills.first)"/>
<path d="\(bData)" fill="\(fills.b)"/>
"""
// The partial M comes first: in touch and overlap it runs under the B's stem.
svg = groupPattern.stringByReplacingMatches(in: svg, range: NSRange(svg.startIndex..., in: svg),
                                            withTemplate: "$1\(NSRegularExpression.escapedTemplate(for: paths))$4")
// Figma sizes the inner-shadow filter to the glyphs' bounds plus 3 px right and below.
func f3(_ v: Double) -> String { String(format: "%.3f", v) }
let bounds = glyphs.first.boundingBoxOfPath.union(glyphs.b.boundingBoxOfPath)
let filterPattern = try NSRegularExpression(pattern: #"<filter id="\#(filterID)" x="[^"]*" y="[^"]*" width="[^"]*" height="[^"]*""#)
guard filterPattern.firstMatch(in: svg, range: NSRange(svg.startIndex..., in: svg)) != nil else { fail("no filter #\(filterID)") }
let region = #"<filter id="\#(filterID)" x="\#(f3(bounds.minX))" y="\#(f3(bounds.minY))" width="\#(f3(bounds.width + 3))" height="\#(f3(bounds.height + 3))""#
svg = filterPattern.stringByReplacingMatches(in: svg, range: NSRange(svg.startIndex..., in: svg),
                                             withTemplate: NSRegularExpression.escapedTemplate(for: region))
let generated = "<!-- Generated by make-glyphs.swift from \(paramsURL.lastPathComponent) and base-\(params.variant).svg: edit those, not this file. -->\n"
if let firstLineEnd = svg.firstIndex(of: "\n") { svg.insert(contentsOf: "\n" + generated.dropLast(), at: firstLineEnd) }
try svg.write(toFile: arguments[1], atomically: true, encoding: .utf8)

let d = Dictionary(glyphs.dims, uniquingKeysWith: { a, _ in a })
if let path = options["--guides"] {
    let top = d["top"]!, base = d["baseline"]!, hw = d["hw"]!, start = d["start"]!, xm = d["xm"]!, t = d["tanTheta"]!
    func line(_ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double, _ color: String) -> String {
        #"<path d="M\#(f3(x0)) \#(f3(y0))L\#(f3(x1)) \#(f3(y1))" stroke="\#(color)" stroke-width="0.6"/>"#
    }
    var lines: [String] = []
    for key in ["top", "baseline", "crotchY", "vertexY", "barTop", "barBottom"] {
        if let y = d[key] { lines.append(line(110, y, 402, y, "#00D8FF")) }
    }
    for key in ["x0", "stemRight", "rightEdge", "xB", "xBRight"] { lines.append(line(d[key]!, 140, d[key]!, 372, "#00D8FF")) }
    lines.append(line(xm, 140, xm, 372, "#FF5C8A"))
    let ya = top - 40, yb = base + 20
    for offset in [0.0, -hw] {
        let u0 = start + offset + (ya - top) * t, u1 = start + offset + (yb - top) * t
        lines.append(line(u0, ya, u1, yb, "#FF5C8A"))
        lines.append(line(2 * xm - u0, ya, 2 * xm - u1, yb, "#FF5C8A"))
    }
    if let shift = d["channelHorizontal"] {
        let u0 = 2 * xm - (start + (ya - top) * t) + hw + shift, u1 = 2 * xm - (start + (yb - top) * t) + hw + shift
        lines.append(line(u0, ya, u1, yb, "#00D8FF"))
    }
    try ("<svg width=\"512\" height=\"512\" viewBox=\"0 0 512 512\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">\n"
        + lines.joined(separator: "\n") + "\n</svg>\n").write(toFile: path, atomically: true, encoding: .utf8)
}
var report = glyphs.dims.map { "\($0.0)=\(f3($0.1))" }
report.append("gap=\(f3(params.gap))")
report.append("inkLeft=\(f3(bounds.minX))")
report.append("inkRight=\(f3(bounds.maxX))")
report.append("inkWidth=\(f3(bounds.width))")
if let path = options["--dims"] { try (report.joined(separator: "\n") + "\n").write(toFile: path, atomically: true, encoding: .utf8) }
// The mark alone, for the app's title bar: the same path data and fills the master's glyph
// group holds, so the two cannot drift apart unnoticed (AppIconMarkTests compares them).
if let path = options["--swift"] {
    let swift = """
    // Generated by AppIcon/make-glyphs.swift from \(paramsURL.lastPathComponent): edit that, not this file.
    // scripts/build-icon.sh regenerates it with the masters.
    import CoreGraphics

    nonisolated extension AppIconMark {
        /// The partial M as the master's glyph group draws it.
        public static let partialM = Glyph(
            path: "\(firstData)",
            fill: "\(fills.first)")
        /// The B as the master's glyph group draws it.
        public static let b = Glyph(
            path: "\(bData)",
            fill: "\(fills.b)")
        /// The mark's ink in the master's 512-unit space, y down: from the partial M's stem to
        /// the B's bowl, and from the cap line to the baseline.
        public static let ink = CGRect(
            x: \(number(bounds.minX)), y: \(number(bounds.minY)), width: \(number(bounds.width)), height: \(number(bounds.height)))
    }

    """
    try swift.write(toFile: path, atomically: true, encoding: .utf8)
}

print("\(arguments[1]): \(params.variant), junction \(params.junction), fills \(fills.first) \(fills.b)")
print("  " + report.joined(separator: " "))
for note in glyphs.notes { print("  note: \(note)") }
