import Foundation
import simd

// Route preview math checks (no ARKit). Run in CI with:
// swiftc Fuga/Navigation/RouteTracker.swift Fuga/Localization/RoutePreviewMath.swift tests/route_preview/main.swift

func expect(_ condition: Bool, _ message: String) { precondition(condition, message) }
func near(_ a: Double, _ b: Double, _ tol: Double = 1e-3) -> Bool { abs(a - b) <= tol }

/// scan-from-AR: rotate about +y (counter-clockwise seen from above) then translate.
func scanFromAR(yawDegrees: Float, translation t: SIMD3<Float>) -> simd_float4x4 {
    let r = yawDegrees * .pi / 180
    var m = matrix_identity_float4x4
    m.columns.0 = SIMD4(cos(r), 0, -sin(r), 0)
    m.columns.2 = SIMD4(sin(r), 0, cos(r), 0)
    m.columns.3 = SIMD4(t.x, t.y, t.z, 1)
    return m
}

// 1. Identity alignment: scan (x, z) -> ARKit top-down (x, -z).
let id = RoutePreviewMath.arTopDown(scanXZ: [[1, 2], [3, -4]], scanY: 0, scanFromAR: matrix_identity_float4x4)!
expect(near(id[0].x, 1) && near(id[0].y, -2) && near(id[1].x, 3) && near(id[1].y, 4), "identity top-down")

// 2. Rotated + translated alignment round-trips AR points.
let T = scanFromAR(yawDegrees: 37, translation: SIMD3(15.4, 3.5, 25.1))
let arPoints: [SIMD4<Float>] = [SIMD4(11.2, 0.8, -6.1, 1), SIMD4(4, 0.8, 2, 1)]
let scanXZ = arPoints.map { p -> [Double] in let s = T * p; return [Double(s.x), Double(s.z)] }
let back = RoutePreviewMath.arTopDown(scanXZ: scanXZ, scanY: Double((T * arPoints[0]).y), scanFromAR: T)!
for (p, q) in zip(arPoints, back) {
    expect(near(Double(p.x), q.x, 1e-3) && near(Double(-p.z), q.y, 1e-3), "round trip through alignment")
}
expect(RoutePreviewMath.arTopDown(scanXZ: [[1, 2]], scanY: 0, scanFromAR: T) == nil, "need two points")
expect(RoutePreviewMath.arTopDown(scanXZ: [[1, .nan], [2, 2]], scanY: 0, scanFromAR: T) == nil, "reject non-finite")

// 3. Camera pose in scan frame: an ARKit camera looks along its -Z.
var cam = matrix_identity_float4x4; cam.columns.3 = SIMD4(1, 1.4, 2, 1)
let pose = RoutePreviewMath.scanPose(arCamera: cam, scanFromAR: matrix_identity_float4x4)
expect(pose.forward == SIMD3(0, 0, -1) && pose.position == SIMD3(1, 1.4, 2), "camera forward is -Z")
let rotated = RoutePreviewMath.scanPose(arCamera: cam, scanFromAR: scanFromAR(yawDegrees: 90, translation: .zero))
expect(abs(rotated.forward.x + 1) < 1e-5 && abs(rotated.forward.z) < 1e-5, "yaw 90 turns -Z to -X")

// 4. Along-route measurements on an L-shaped path.
let path = RoutePreviewMath.withAlong([Vec2(x: 0, y: 0), Vec2(x: 10, y: 0), Vec2(x: 10, y: 5)])
expect(near(path[2].along, 15), "along accumulates")
let hit = RoutePreviewMath.project(Vec2(x: 4, y: 1), on: path)
expect(near(hit.along, 4) && near(hit.offset, 1) && hit.segment == 0, "projection")
let rest = RoutePreviewMath.remaining(from: Vec2(x: 4, y: 1), on: path)
expect(rest.count == 3 && near(rest[0].point.x, 4) && near(rest[0].point.y, 0) && near(rest[0].along, 4), "remaining starts at closest point")
let aim = RoutePreviewMath.point(on: path, along: 12)!
expect(near(aim.x, 10) && near(aim.y, 2), "point along route turns the corner")
expect(RoutePreviewMath.point(on: path, along: 99)! == Vec2(x: 10, y: 5), "clamped to end")

// 5. Arrow convention: identity ARKit camera looks along -Z, i.e. top-down heading 90 deg.
//    A route toward +x is then 90 deg to the right (clockwise positive).
expect(near(RouteTracker.relativeBearing(from: Vec2(x: 0, y: 0), headingDegrees: 90, to: Vec2(x: 2, y: 0)), 90), "right is positive")
expect(near(RouteTracker.relativeBearing(from: Vec2(x: 0, y: 0), headingDegrees: 90, to: Vec2(x: -2, y: 0)), -90), "left is negative")

print("Route preview math checks passed")
