import Foundation
import simd

/// Math for the draft route preview: turns a route given in the scan's coordinates into the
/// phone's live ARKit world, and measures where the phone is along it. No ARKit or UI here,
/// so it compiles and is tested with plain swiftc. Top-down points are ARKit (x, -z), the
/// same frame `RouteNavigator.topDownPose` and `FloorPathNode` use.
enum RoutePreviewMath {
    /// Scan-frame route (x, z) pairs to ARKit top-down points, using the capture-time
    /// scan-from-AR alignment. `scanY` is any height in the scan frame (the alignment is
    /// level, so it barely matters; the floor line uses ARKit's own floor height).
    static func arTopDown(scanXZ: [[Double]], scanY: Double, scanFromAR: simd_float4x4) -> [Vec2]? {
        let arFromScan = simd_inverse(scanFromAR)
        var points: [Vec2] = []
        for xz in scanXZ {
            guard xz.count == 2, xz[0].isFinite, xz[1].isFinite else { return nil }
            let p = arFromScan * SIMD4<Float>(Float(xz[0]), Float(scanY), Float(xz[1]), 1)
            points.append(Vec2(x: Double(p.x), y: Double(-p.z)))
        }
        return points.count >= 2 ? points : nil
    }

    /// The phone's ARKit camera pose in scan coordinates: position and the direction the
    /// back camera faces (ARKit cameras look along their -Z axis).
    static func scanPose(arCamera: simd_float4x4, scanFromAR: simd_float4x4) -> (position: SIMD3<Float>, forward: SIMD3<Float>) {
        let scanCamera = scanFromAR * arCamera
        let p = scanCamera.columns.3, back = scanCamera.columns.2
        return (SIMD3(p.x, p.y, p.z), SIMD3(-back.x, -back.y, -back.z))
    }

    static func withAlong(_ points: [Vec2]) -> [PathPoint] {
        var along = 0.0
        return points.enumerated().map { (i, p) -> PathPoint in
            if i > 0 { along += (p - points[i - 1]).length }
            return PathPoint(point: p, along: along)
        }
    }

    /// Closest point on the route: distance along it, sideways offset, and the segment index.
    static func project(_ p: Vec2, on path: [PathPoint]) -> (along: Double, offset: Double, segment: Int) {
        var best = (along: 0.0, offset: Double.infinity, segment: 0)
        for i in 0..<max(path.count - 1, 0) {
            let a = path[i].point, ab = path[i + 1].point - a
            let len2 = ab.dot(ab)
            let t = len2 > 0 ? min(1, max(0, (p - a).dot(ab) / len2)) : 0
            let closest = a + ab * t
            let d = (p - closest).length
            if d < best.offset { best = (path[i].along + t * len2.squareRoot(), d, i) }
        }
        return best
    }

    /// The part of the route still ahead, starting at the closest point to `p`.
    static func remaining(from p: Vec2, on path: [PathPoint]) -> [PathPoint] {
        guard path.count >= 2 else { return path }
        let hit = project(p, on: path)
        let a = path[hit.segment], b = path[hit.segment + 1]
        let span = b.along - a.along
        let t = span > 0 ? (hit.along - a.along) / span : 0
        let start = PathPoint(point: a.point + (b.point - a.point) * t, along: hit.along)
        return [start] + path[(hit.segment + 1)...]
    }

    /// The route point `meters` further along than `along` (or the end), for the arrow to aim at.
    static func point(on path: [PathPoint], along target: Double) -> Vec2? {
        guard let last = path.last else { return nil }
        guard target < last.along else { return last.point }
        for i in 0..<(path.count - 1) where path[i + 1].along >= target {
            let a = path[i], b = path[i + 1], span = b.along - a.along
            let t = span > 0 ? (target - a.along) / span : 0
            return a.point + (b.point - a.point) * t
        }
        return last.point
    }
}
