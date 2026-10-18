import Foundation

/// A rigid transform between ARKit top-down meters (x, -z) and plan meters.
/// Never modified by assumptions about which corridor the user must be following.
struct PlanAlignment {
    var arOrigin: Vec2
    var planOrigin: Vec2
    var rotationDegrees: Double

    func toPlan(_ ar: Vec2) -> Vec2 {
        planOrigin + (ar - arOrigin).rotated(byDegrees: rotationDegrees)
    }

    func toAR(_ plan: Vec2) -> Vec2 {
        arOrigin + (plan - planOrigin).rotated(byDegrees: -rotationDegrees)
    }

    static func cameraHeading(forward: Vec2) -> Double? {
        guard forward.x.isFinite, forward.y.isFinite, forward.length >= 0.5 else { return nil }
        return forward.angleDegrees
    }
}
