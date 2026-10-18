import Foundation

/// 2D point/vector in plan meters.
struct Vec2: Equatable {
    var x: Double
    var y: Double

    static func + (a: Vec2, b: Vec2) -> Vec2 { Vec2(x: a.x + b.x, y: a.y + b.y) }
    static func - (a: Vec2, b: Vec2) -> Vec2 { Vec2(x: a.x - b.x, y: a.y - b.y) }
    static func * (a: Vec2, k: Double) -> Vec2 { Vec2(x: a.x * k, y: a.y * k) }
    var length: Double { (x * x + y * y).squareRoot() }
    func dot(_ b: Vec2) -> Double { x * b.x + y * b.y }
    /// Math angle in degrees: 0 = +x, counter-clockwise positive.
    var angleDegrees: Double { atan2(y, x) * 180 / .pi }
    func rotated(byDegrees deg: Double) -> Vec2 {
        let r = deg * .pi / 180
        return Vec2(x: x * cos(r) - y * sin(r), y: x * sin(r) + y * cos(r))
    }
}

/// Pure route geometry: where you are along the route, what's ahead, where the turns are.
/// No ARKit or UI here, so the same logic can be checked offline against a recorded walk.
struct RouteTracker {
    struct Turn {
        let vertex: Int
        let distanceAlong: Double
        /// Signed degrees, positive = left (counter-clockwise on the plan).
        let degrees: Double
        let nextStretchMeters: Double

        var direction: String { degrees > 0 ? "left" : "right" }
        var spokenTurn: String { abs(degrees) < 60 ? "turn slightly \(direction)" : "turn \(direction)" }
    }

    let points: [Vec2]
    private let cumulative: [Double]
    let total: Double
    let turns: [Turn]
    /// Index of the segment we were last on; keeps progress from jumping backwards.
    private(set) var segment = 0

    init(points: [Vec2], minTurnDegrees: Double = 25) {
        self.points = points
        var cum: [Double] = [0]
        for i in 1..<points.count {
            cum.append(cum[i - 1] + (points[i] - points[i - 1]).length)
        }
        cumulative = cum
        total = cum.last ?? 0

        var found: [Turn] = []
        if points.count >= 3 {
            for k in 1..<(points.count - 1) {
                let a = (points[k] - points[k - 1]).angleDegrees
                let b = (points[k + 1] - points[k]).angleDegrees
                let d = RouteTracker.wrap(b - a)
                if abs(d) >= minTurnDegrees {
                    found.append(Turn(vertex: k, distanceAlong: cum[k], degrees: d,
                                      nextStretchMeters: cum[k + 1] - cum[k]))
                }
            }
        }
        turns = found
    }

    /// Wraps degrees into (-180, 180].
    static func wrap(_ d: Double) -> Double {
        var v = d.truncatingRemainder(dividingBy: 360)
        if v > 180 { v -= 360 }
        if v <= -180 { v += 360 }
        return v
    }

    /// Projects a position onto the route. Returns distance along the route and how far off it you are.
    mutating func project(_ p: Vec2) -> (along: Double, offRoute: Double) {
        func closest(on i: Int) -> (along: Double, dist: Double) {
            let a = points[i], b = points[i + 1]
            let ab = b - a
            let len2 = max(ab.dot(ab), 1e-9)
            let t = min(1, max(0, (p - a).dot(ab) / len2))
            let q = a + ab * t
            return (cumulative[i] + t * len2.squareRoot(), (p - q).length)
        }
        // Look near the current segment first so a corridor next to the route can't steal progress.
        let lo = max(0, segment - 1)
        let hi = min(points.count - 2, segment + 2)
        var best = (seg: segment, along: 0.0, dist: Double.infinity)
        for i in lo...hi {
            let c = closest(on: i)
            if c.dist < best.dist { best = (i, c.along, c.dist) }
        }
        // If we're far from the nearby segments, search the whole route.
        if best.dist > 4 {
            for i in 0..<(points.count - 1) {
                let c = closest(on: i)
                if c.dist < best.dist { best = (i, c.along, c.dist) }
            }
        }
        segment = best.seg
        return (best.along, best.dist)
    }

    /// The point a given distance along the route.
    func point(at along: Double) -> Vec2 {
        let s = min(max(0, along), total)
        for i in 0..<(points.count - 1) where s <= cumulative[i + 1] {
            let segLen = cumulative[i + 1] - cumulative[i]
            let t = segLen > 0 ? (s - cumulative[i]) / segLen : 0
            return points[i] + (points[i + 1] - points[i]) * t
        }
        return points.last ?? Vec2(x: 0, y: 0)
    }

    /// Which way the arrow should point (plan degrees), following the drawn path:
    /// along the hallway you're in, switching to the next hallway just before the corner,
    /// with a small nudge back toward the path's centerline if you've drifted to one side
    /// (never more than 35°, so it doesn't point you into a wall).
    func pathDirection(at along: Double, position p: Vec2, switchAhead: Double = 0.8) -> Double {
        guard points.count >= 2 else { return 0 }
        let s = min(max(0, along + switchAhead), total - 1e-6)
        var i = 0
        while i < points.count - 2 && s > cumulative[i + 1] { i += 1 }
        let a = points[i], ab = points[i + 1] - a
        let len = max(ab.length, 1e-6)
        // Signed distance from the segment's line: positive = you're to its left.
        let left = (ab.x * (p.y - a.y) - ab.y * (p.x - a.x)) / len
        let nudge = max(-35, min(35, atan2(left, 3) * 180 / .pi))
        return RouteTracker.wrap(ab.angleDegrees - nudge)
    }

    /// The rest of the route from a distance along it: points and how far along each one is.
    func remainingPath(from along: Double) -> [(point: Vec2, along: Double)] {
        let s = min(max(0, along), total)
        var out = [(point(at: s), s)]
        for i in 0..<points.count where cumulative[i] > s + 0.05 {
            out.append((points[i], cumulative[i]))
        }
        return out
    }

    /// The next turn ahead of a distance along the route.
    func nextTurn(after along: Double) -> Turn? {
        turns.first { $0.distanceAlong > along - 0.5 }
    }

    /// The nearby route segment that a straight stretch of walking most likely followed.
    /// Used to correct the starting heading: hallways are straight, so if you walk 3 m in a
    /// straight line next to a long route segment, you were walking along it.
    /// Returns how far (degrees) the walk is turned from that segment and the closest point on it.
    func bestParallelSegment(near p: Vec2, walkingDegrees: Double,
                             maxDistance: Double = 7, minLength: Double = 4,
                             maxDelta: Double = 40) -> (delta: Double, closest: Vec2)? {
        var best: (delta: Double, closest: Vec2)?
        for i in 0..<(points.count - 1) {
            let a = points[i]
            let ab = points[i + 1] - a
            let len = ab.length
            guard len >= minLength else { continue }
            let t = min(1, max(0, (p - a).dot(ab) / (len * len)))
            let q = a + ab * t
            guard (p - q).length <= maxDistance else { continue }
            let d = RouteTracker.wrap(ab.angleDegrees - walkingDegrees)
            if abs(d) < maxDelta, best == nil || abs(d) < abs(best!.delta) {
                best = (d, q)
            }
        }
        return best
    }

    /// Bearing for the arrow: degrees from the way the phone faces to the target,
    /// positive = clockwise (to the right), as ExitArrowView expects.
    static func relativeBearing(from position: Vec2, headingDegrees: Double, to target: Vec2) -> Double {
        let targetAngle = (target - position).angleDegrees
        // Plan angles are counter-clockwise; the arrow wants clockwise-positive.
        return wrap(headingDegrees - targetAngle)
    }
}
